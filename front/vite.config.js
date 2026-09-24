import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	// The same API_URL as $env/static/private (front/.env, or a real variable, which wins).
	const api = loadEnv(mode, process.cwd(), '').API_URL || 'http://localhost:3003';

	return {
		plugins: [sveltekit(), svelteTesting()],
		server: {
			host: '0.0.0.0',
			port: 5173,
			proxy: {
				// The payloads carry site-relative photo URLs (/media/avatars/…): nginx serves
				// them in prod, the API (Django serves media when ENV=dev) behind this in dev.
				// changeOrigin: the API's ALLOWED_HOSTS knows its own host, not the dev server's.
				'/media': { target: api, changeOrigin: true }
			}
		},
		test: {
			environment: 'jsdom',
			include: ['src/**/*.test.js'],
			setupFiles: ['src/setupTests.js'],
			clearMocks: true,
			restoreMocks: true
		}
	};
});
