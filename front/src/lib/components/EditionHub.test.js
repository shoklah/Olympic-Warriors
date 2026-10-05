import { screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import EditionHub from './EditionHub.svelte';
import { summary } from '../fixtures/summary.js';

const editions = [
	{ id: 1, year: 2026, host: 'Paris', photos_url: null },
	{ id: 2, year: 2025, host: 'Lyon', photos_url: null },
	{ id: 3, year: 2024, host: 'Nantes', photos_url: null }
];

describe('EditionHub', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('shows a countdown before the start', () => {
		vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByText('Days').querySelector('span')).toHaveTextContent(/^2$/);
		expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
	});

	it('shows the ranking button once started', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('href', '/2026/ranking');
		expect(screen.queryByText('Days')).toBeNull();
	});

	it('shows host, dates, discipline icons and every edition with the current one marked', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByText('Paris · 19 – 20 September 2026')).toBeInTheDocument();
		expect(screen.getByAltText('Relay')).toHaveAttribute('src', expect.stringMatching(/relay\.svg$/));
		expect(screen.getByAltText('Orienteering')).toHaveAttribute('src', expect.stringMatching(/orienteering\.svg$/));
		const pills = screen.getByRole('navigation', { name: 'Editions' });
		expect(within(pills).getAllByRole('link').map((a) => a.textContent.trim())).toEqual([
			'2026',
			'2025',
			'2024'
		]);
		const current = screen.getByRole('link', { name: '2026' });
		expect(current).toHaveAttribute('href', '/2026');
		expect(current).toHaveAttribute('aria-current', 'page');
		expect(current).toHaveClass('current');
		expect(screen.getByRole('link', { name: '2025' })).toHaveAttribute('href', '/2025');
		expect(screen.getByRole('link', { name: '2025' })).not.toHaveAttribute('aria-current');
	});

	it('marks itself always dark, the selector styles.css keeps the dark tokens on', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		const { container } = renderWith(EditionHub, { summary, editions });

		expect(container.querySelector('[data-always-dark]')).not.toBeNull();
	});

	it('hides the edition pills when there is a single edition', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions: [editions[0]] });

		expect(screen.queryByRole('navigation', { name: 'Editions' })).toBeNull();
	});

	it('prints one date when the edition lasts a single day', () => {
		vi.setSystemTime(new Date(2026, 8, 19, 10, 0, 0));
		const oneDay = {
			...summary,
			edition: { ...summary.edition, start_date: '2026-09-19', end_date: '2026-09-19' }
		};
		renderWith(EditionHub, { summary: oneDay, editions });

		expect(screen.getByText('Paris · 19 September 2026')).toBeInTheDocument();
	});

	it('ticks and flips to the ranking button when the start passes', async () => {
		vi.setSystemTime(new Date('2026-09-19T06:59:59Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByText('Seconds').querySelector('span')).toHaveTextContent(/^1$/);

		await vi.advanceTimersByTimeAsync(1000);

		expect(screen.getByRole('link', { name: 'Ranking' })).toBeInTheDocument();
		expect(screen.queryByText('Days')).toBeNull();
	});

	it('speaks French under fr', () => {
		vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
		renderWith(EditionHub, { summary, editions }, 'fr');

		expect(screen.getByText('Paris · 19 – 20 septembre 2026')).toBeInTheDocument();
		expect(screen.getByText('Jours').querySelector('span')).toHaveTextContent(/^2$/);
		expect(screen.getByAltText('Relais')).toBeInTheDocument();
		expect(screen.getByRole('navigation', { name: 'Éditions' })).toBeInTheDocument();
	});

	it('links the players leaderboard before the start, while the ranking waits', () => {
		vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
		expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
	});

	it('links the players leaderboard beside the ranking once started', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('href', '/2026/ranking');
		expect(screen.getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
	});

	it('words the players link in French', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		renderWith(EditionHub, { summary, editions }, 'fr');

		expect(screen.getByRole('link', { name: 'Joueurs' })).toHaveAttribute('href', '/players');
	});
	describe('with unconfirmed dates', () => {
		const unconfirmed = { ...summary, edition: { ...summary.edition, dates_confirmed: false } };

		it('hides the countdown and the date range', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary: unconfirmed, editions });

			expect(screen.getByText('Paris · Dates to be announced')).toBeInTheDocument();
			expect(screen.queryByText('Days')).toBeNull();
			expect(screen.queryByText(/September/)).toBeNull();
		});

		it('never offers the ranking, even once the provisional start has passed', () => {
			vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
			renderWith(EditionHub, { summary: unconfirmed, editions });

			expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
			expect(screen.getByRole('link', { name: 'Players' })).toBeInTheDocument();
		});

		it('says it in French', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary: unconfirmed, editions }, 'fr');

			expect(screen.getByText('Paris · Dates à venir')).toBeInTheDocument();
		});

		it('treats a payload without the flag as confirmed', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions });

			expect(screen.getByText('Paris · 19 – 20 September 2026')).toBeInTheDocument();
		});
	});

	describe('registration link', () => {
		// The latest edition (2026, starting 2026-09-19) with its public window set.
		const withWindow = [
			{ ...editions[0], start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null },
			...editions.slice(1)
		];
		const player = { id: 1, first_name: 'Léa', last_name: 'Martin', can_register: true };

		it('sends a visitor through the login while registration is open', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions: withWindow, me: null });

			expect(screen.getByRole('link', { name: 'Log in to register' })).toHaveAttribute(
				'href', '/login?next=/register'
			);
		});

		it('links someone who can register straight to the form', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions: withWindow, me: player });

			expect(screen.getByRole('link', { name: 'Registration 2026' })).toHaveAttribute('href', '/register');
		});

		it('shows nothing to someone who cannot register', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions: withWindow, me: { ...player, can_register: false } });

			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
		});

		it('shows nothing once the window has closed, before it opens, or when it is not set', () => {
			vi.setSystemTime(new Date('2026-09-19T08:00:00Z')); // the day of the start: closed
			const closed = renderWith(EditionHub, { summary, editions: withWindow, me: null });
			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
			closed.unmount();

			vi.setSystemTime(new Date('2025-12-31T12:00:00Z'));
			const early = renderWith(EditionHub, { summary, editions: withWindow, me: null });
			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
			early.unmount();

			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions, me: null }); // no registration_opens at all
			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
		});

		it('is only on the latest edition hub', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			const older = { ...summary, edition: { ...summary.edition, year: 2025 } };
			renderWith(EditionHub, { summary: older, editions: withWindow, me: null });

			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
		});

		it('says it in French', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			const visitor = renderWith(EditionHub, { summary, editions: withWindow, me: null }, 'fr');
			expect(screen.getByRole('link', { name: "Se connecter pour s'inscrire" })).toBeInTheDocument();
			visitor.unmount();

			renderWith(EditionHub, { summary, editions: withWindow, me: player }, 'fr');
			expect(screen.getByRole('link', { name: 'Inscription 2026' })).toBeInTheDocument();
		});
	});
});
