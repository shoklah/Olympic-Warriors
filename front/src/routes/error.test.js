import { screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import ErrorPage from './+error.svelte';

const state = { status: 404, error: { message: 'Team not found' } };
vi.mock('$app/stores', async () => {
	const { readable } = await import('svelte/store');
	return { page: readable(new Proxy({}, { get: (_, key) => state[key] })) };
});

describe('error page', () => {
	it('words a 404 from the dictionary in French', () => {
		state.status = 404;
		renderWith(ErrorPage, {}, 'fr');

		expect(screen.getByRole('heading', { name: '404' })).toBeInTheDocument();
		expect(screen.getByText('Page introuvable')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Retour aux Olympic Warriors' })).toHaveAttribute('href', '/');
	});

	it('words a 404 in English under en', () => {
		state.status = 404;
		renderWith(ErrorPage, {}, 'en');

		expect(screen.getByText('Page not found')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Back to the Olympic Warriors' })).toBeInTheDocument();
	});

	it('never shows the raw English message of another error outside dev', () => {
		state.status = 502;
		state.error = { message: 'API unreachable' };
		vi.stubEnv('DEV', false);
		renderWith(ErrorPage, {}, 'fr');

		expect(screen.getByRole('heading', { name: '502' })).toBeInTheDocument();
		expect(screen.getByText('Une erreur est survenue')).toBeInTheDocument();
		expect(screen.queryByText('API unreachable')).toBeNull();
	});
});
