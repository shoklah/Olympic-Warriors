import { describe, expect, it, vi } from 'vitest';
import { actions } from './+page.server.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/2026/disciplines/10', { method: 'POST', body });
};

const call = (action, fields, { token = 'abc', response = json(200, {}) } = {}) => {
	const fetch = vi.fn().mockResolvedValue(response);
	const cookies = { get: (name) => (name === 'token' ? token : undefined) };
	return actions[action]({ cookies, request: post(fields), fetch }).then((result) => ({ result, fetch }));
};

describe('discipline actions', () => {
	it('score patches the game with both scores and the played flag', async () => {
		const { result, fetch } = await call('score', { game: '201', score1: '7', score2: '3', is_played: 'on' });
		expect(result).toEqual({ ok: true, action: 'score', id: 201 });
		expect(fetch).toHaveBeenCalledWith('http://api/game/201/score/', expect.objectContaining({
			method: 'PATCH',
			headers: { 'content-type': 'application/json', authorization: 'Token abc' },
			body: JSON.stringify({ score1: 7, score2: 3, is_played: true })
		}));
	});

	it('score sends is_played false when the switch is off', async () => {
		const { fetch } = await call('score', { game: '201', score1: '0', score2: '0' });
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ score1: 0, score2: 0, is_played: false });
	});

	it('result sends points, or a time, and null for an empty field', async () => {
		let { fetch } = await call('result', { result: '106', kind: 'PTS', value: '12' });
		expect(fetch.mock.calls[0][0]).toBe('http://api/result/106/value/');
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ points: 12 });
		({ fetch } = await call('result', { result: '103', kind: 'TIM', value: '13:15' }));
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ time: '13:15' });
		({ fetch } = await call('result', { result: '103', kind: 'TIM', value: '' }));
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ time: null });
	});

	it('reveal and close patch their rows', async () => {
		let { fetch } = await call('reveal', { discipline: '12', reveal_score: 'true' });
		expect(fetch.mock.calls[0][0]).toBe('http://api/discipline/12/reveal/');
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ reveal_score: true });
		({ fetch } = await call('close', { round: '22' }));
		expect(fetch.mock.calls[0][0]).toBe('http://api/round/22/close/');
	});

	it('refuses a non-numeric or negative value before calling the API', async () => {
		let { result, fetch } = await call('score', { game: '201', score1: 'x', score2: '3' });
		expect(result).toMatchObject({ status: 400, data: { action: 'score', id: 201, error: 'orga.error.invalid' } });
		expect(fetch).not.toHaveBeenCalled();
		({ result } = await call('result', { result: '106', kind: 'PTS', value: '-2' }));
		expect(result).toMatchObject({ status: 400, data: { error: 'orga.error.invalid' } });
	});

	it('fails with the unauthorised key without a cookie', async () => {
		// `token: null`, not `undefined`: the call() helper's default parameter would
		// otherwise still substitute 'abc' for an explicit `undefined` (standard JS
		// destructuring-default semantics), silently defeating this "no cookie" case.
		const { result } = await call('close', { round: '22' }, { token: null });
		expect(result).toMatchObject({ status: 401, data: { action: 'close', id: 22, error: 'orga.error.unauthorised' } });
	});

	it('maps API errors to dictionary keys', async () => {
		const cases = [
			[400, 'orga.error.invalid'],
			[401, 'orga.error.unauthorised'],
			[403, 'orga.error.forbidden'],
			[409, 'orga.error.conflict'],
			[502, 'orga.error.failed']
		];
		for (const [status, key] of cases) {
			const { result } = await call('close', { round: '22' }, { response: json(status, { error: 'x' }) });
			expect(result).toMatchObject({ status, data: { error: key } });
		}
	});
});
