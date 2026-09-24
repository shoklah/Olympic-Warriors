import { screen, within } from '@testing-library/svelte';
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

	it('offers both themes through one form; the stylesheet shows one of the two', () => {
		renderWith(Header, {}, 'en');

		const form = screen.getByRole('form', { name: 'Theme' });
		expect(form).toHaveAttribute('action', '/theme');
		expect(form).toHaveAttribute('method', 'POST');
		expect(form.querySelector('input[name="redirectTo"]')).toHaveValue('/2026/ranking?tab=all');
		expect(within(form).getByRole('button', { name: 'Switch to light theme' })).toHaveValue('light');
		expect(within(form).getByRole('button', { name: 'Switch to dark theme' })).toHaveValue('dark');
	});

	it('words the theme switch in French', () => {
		renderWith(Header, {}, 'fr');

		const form = screen.getByRole('form', { name: 'Thème' });
		expect(within(form).getByRole('button', { name: 'Passer au thème clair' })).toHaveValue('light');
		expect(within(form).getByRole('button', { name: 'Passer au thème sombre' })).toHaveValue('dark');
	});

	it('shows the ORGA pill with a logout form to an organiser', () => {
		renderWith(Header, {}, 'fr', true);

		const button = screen.getByRole('button', { name: 'Orga · Se déconnecter' });
		const form = button.closest('form');
		expect(form).toHaveAttribute('action', '/logout');
		expect(form.querySelector('input[name="redirectTo"]')).toHaveValue('/2026/ranking?tab=all');
	});

	it('shows a login link instead of the pill to a visitor', () => {
		renderWith(Header, {}, 'en');
		expect(screen.queryByRole('button', { name: /Log out/ })).toBeNull();
		expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login');
	});

	it('hides the login link from an organiser and words it in French', () => {
		renderWith(Header, {}, 'fr', true);
		expect(screen.queryByRole('link', { name: /Connexion/ })).toBeNull();

		renderWith(Header, {}, 'fr');
		expect(screen.getByRole('link', { name: 'Connexion' })).toHaveAttribute('href', '/login');
	});

	it('links the players leaderboard after the disciplines, outside any year', () => {
		renderWith(Header, {}, 'en');

		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect(within(nav).getAllByRole('link').map((a) => a.textContent.trim())).toEqual([
			'Ranking',
			'Disciplines',
			'Players',
			'Photos'
		]);
		const players = screen.getByRole('link', { name: 'Players' });
		expect(players).toHaveAttribute('href', '/players');
		expect(players).not.toHaveAttribute('aria-current');
	});

	it('words the players tab in French', () => {
		renderWith(Header, {}, 'fr');

		expect(screen.getByRole('link', { name: 'Joueurs' })).toHaveAttribute('href', '/players');
	});
});
