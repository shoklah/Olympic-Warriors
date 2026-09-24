import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import { handle } from './hooks.server.js';

const HTML = '<html lang="%lang%" data-theme="%theme%">';

const run = (cookies) => {
	const event = { cookies: { get: (name) => cookies[name] }, setHeaders: vi.fn() };
	const resolve = (_event, opts) => opts.transformPageChunk({ html: HTML });
	return handle({ event, resolve }).then((html) => ({ html, event }));
};

describe('handle', () => {
	it('fills the html lang from the cookie, French by default', async () => {
		expect((await run({ lang: 'en' })).html).toBe('<html lang="en" data-theme="system">');
		expect((await run({})).html).toBe('<html lang="fr" data-theme="system">');
		expect((await run({ lang: 'de' })).html).toBe('<html lang="fr" data-theme="system">');
	});

	it('fills the html theme from the cookie, the device setting by default', async () => {
		expect((await run({ theme: 'light' })).html).toBe('<html lang="fr" data-theme="light">');
		expect((await run({ theme: 'dark', lang: 'en' })).html).toBe('<html lang="en" data-theme="dark">');
		expect((await run({ theme: 'sepia' })).html).toBe('<html lang="fr" data-theme="system">');
	});

	it('varies the response on the cookie', async () => {
		const { event } = await run({ lang: 'en' });
		expect(event.setHeaders).toHaveBeenCalledWith({ vary: 'Cookie' });
	});

	it('has its placeholders in app.html', () => {
		// Vitest runs from the front root; import.meta.url is a Vite URL here, not file://.
		expect(readFileSync('src/app.html', 'utf8')).toContain(HTML);
	});
});
