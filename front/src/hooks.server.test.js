import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import { handle } from './hooks.server.js';

const run = (lang) => {
	const event = { cookies: { get: () => lang }, setHeaders: vi.fn() };
	const resolve = (_event, opts) => opts.transformPageChunk({ html: '<html lang="%lang%">' });
	return handle({ event, resolve }).then((html) => ({ html, event }));
};

describe('handle', () => {
	it('fills the html lang from the cookie, French by default', async () => {
		expect((await run('en')).html).toBe('<html lang="en">');
		expect((await run(undefined)).html).toBe('<html lang="fr">');
		expect((await run('de')).html).toBe('<html lang="fr">');
	});

	it('varies the response on the cookie', async () => {
		const { event } = await run('en');
		expect(event.setHeaders).toHaveBeenCalledWith({ vary: 'Cookie' });
	});

	it('has its placeholder in app.html', () => {
		// Vitest runs from the front root; import.meta.url is a Vite URL here, not file://.
		expect(readFileSync('src/app.html', 'utf8')).toContain('<html lang="%lang%">');
	});
});
