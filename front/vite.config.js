import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	server: {
		host: '0.0.0.0',
		port: 5173
	},
	test: {
		environment: 'jsdom',
		include: ['src/**/*.test.js'],
		setupFiles: ['src/setupTests.js'],
		clearMocks: true,
		restoreMocks: true
	}
});
