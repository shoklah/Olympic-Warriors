import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createSaver } from './saver.js';

const reply = (status, body) => Promise.resolve({ status, ok: status < 300, json: () => Promise.resolve(body) });

describe('createSaver', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('saves once, debounced, with the version it was based on, and keeps the new one', async () => {
		const fetch = vi.fn(() => reply(200, { document: {}, updated_at: 'v2' }));
		const saved = vi.fn();
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1', onSaved: saved });

		saver.save({ a: 1 });
		saver.save({ a: 2 });
		await vi.advanceTimersByTimeAsync(900);

		expect(fetch).toHaveBeenCalledTimes(1);
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ document: { a: 2 }, based_on: 'v1' });
		expect(saved).toHaveBeenCalledWith('v2');
		saver.save({ a: 3 });
		await vi.advanceTimersByTimeAsync(900);
		expect(JSON.parse(fetch.mock.calls[1][1].body).based_on).toBe('v2');
	});

	it('reports a stale draft with the stored one and stops saving', async () => {
		const fetch = vi.fn(() => reply(409, { error: 'stale_draft', draft: { document: { a: 9 }, updated_at: 'v9' } }));
		const stale = vi.fn();
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1', onStale: stale });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);

		expect(stale).toHaveBeenCalledWith({ document: { a: 9 }, updated_at: 'v9' });
		saver.save({ a: 2 });
		await vi.advanceTimersByTimeAsync(900);
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('reports other failures and lets the next change try again', async () => {
		const fetch = vi.fn(() => reply(500, {}));
		const failed = vi.fn();
		const saver = createSaver({ url: '/x', fetch, based_on: null, onError: failed });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		saver.save({ a: 2 });
		await vi.advanceTimersByTimeAsync(900);

		expect(failed).toHaveBeenCalledTimes(2);
		expect(fetch).toHaveBeenCalledTimes(2);
	});

	it('exposes the version it holds, for an apply to name', async () => {
		const fetch = vi.fn(() => reply(200, { document: {}, updated_at: 'v2' }));
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1' });

		expect(saver.version()).toBe('v1');
		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		expect(saver.version()).toBe('v2');
	});

	it('flush saves a pending change at once', async () => {
		const fetch = vi.fn(() => reply(200, { document: {}, updated_at: 'v2' }));
		const saver = createSaver({ url: '/x', fetch, based_on: null });

		saver.save({ a: 1 });
		await saver.flush();

		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('serialises saves: a second PUT waits for the first and uses the version it returned', async () => {
		let release;
		const fetch = vi
			.fn()
			.mockImplementationOnce(() => new Promise((r) => (release = () => r({ status: 200, ok: true, json: () => Promise.resolve({ updated_at: 'v2' }) }))))
			.mockImplementation(() => reply(200, { updated_at: 'v3' }));
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1' });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		saver.save({ a: 2 });
		let flushed = false;
		const flushing = saver.flush().then(() => (flushed = true));
		await vi.advanceTimersByTimeAsync(0);
		expect(fetch).toHaveBeenCalledTimes(1);
		expect(flushed).toBe(false);

		release();
		await flushing;
		expect(fetch).toHaveBeenCalledTimes(2);
		expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ document: { a: 2 }, based_on: 'v2' });
		expect(saver.version()).toBe('v3');
	});

	it('flush waits for a request already in flight', async () => {
		let release;
		const fetch = vi.fn(() => new Promise((r) => (release = () => r({ status: 200, ok: true, json: () => Promise.resolve({ updated_at: 'v2' }) }))));
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1' });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		let flushed = false;
		const flushing = saver.flush().then(() => (flushed = true));
		await vi.advanceTimersByTimeAsync(0);
		expect(flushed).toBe(false);
		release();
		await flushing;
		expect(saver.version()).toBe('v2');
	});

	it('retries a failed save on the next flush', async () => {
		const fetch = vi.fn().mockImplementationOnce(() => reply(500, {})).mockImplementation(() => reply(200, { updated_at: 'v2' }));
		const saver = createSaver({ url: '/x', fetch, based_on: 'v1' });

		saver.save({ a: 1 });
		await vi.advanceTimersByTimeAsync(900);
		await saver.flush();

		expect(fetch).toHaveBeenCalledTimes(2);
		expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ document: { a: 1 }, based_on: 'v1' });
		expect(saver.version()).toBe('v2');
	});
});
