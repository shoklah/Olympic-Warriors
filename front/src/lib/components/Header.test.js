import { screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Header from './Header.svelte';

vi.mock('$app/stores', async () => {
	const { readable } = await import('svelte/store');
	return {
		page: readable({
			data: {
				editions: [{ id: 1, year: 2026, host: 'Paris', photos_url: 'https://photos.example' }],
				latestYear: 2026
			},
			params: { year: '2026' },
			url: new URL('http://localhost/2026/ranking?tab=all'),
			error: null
		})
	};
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

describe('Header', () => {
	it('shows the language switch with the current language marked', () => {
		renderWith(Header, {}, 'en');

		const form = screen.getByRole('form', { name: 'Language' });
		expect(form).toHaveAttribute('action', '/lang');
		expect(form).toHaveAttribute('method', 'POST');
		expect(form.querySelector('input[name="redirectTo"]')).toHaveValue('/2026/ranking?tab=all');
		expect(screen.getByRole('button', { name: 'EN' })).toHaveAttribute('aria-current', 'true');
		expect(screen.getByRole('button', { name: 'FR' })).not.toHaveAttribute('aria-current');
		expect(screen.getByRole('button', { name: 'FR' })).toHaveValue('fr');
		expect(screen.getByRole('button', { name: 'EN' })).toHaveValue('en');
	});

	it('marks French and translates the tabs under fr', () => {
		renderWith(Header, {}, 'fr');

		expect(screen.getByRole('button', { name: 'FR' })).toHaveAttribute('aria-current', 'true');
		expect(screen.getByRole('link', { name: 'Classement' })).toHaveAttribute('aria-current', 'page');
		expect(screen.queryByRole('link', { name: 'Équipes' })).toBeNull();
		expect(screen.getByRole('link', { name: 'Épreuves' })).toHaveAttribute('href', '/2026/disciplines');
		expect(screen.getByRole('link', { name: 'Photos' })).toHaveAttribute('href', 'https://photos.example');
		expect(screen.getByRole('combobox', { name: 'Édition' })).toHaveValue('2026');
		expect(screen.getByRole('navigation', { name: 'Rubriques' })).toBeInTheDocument();
	});

	it('keeps English tabs under en', () => {
		renderWith(Header, {}, 'en');

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('combobox', { name: 'Edition' })).toBeInTheDocument();
	});
});
