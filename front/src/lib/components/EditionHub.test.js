import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
		render(EditionHub, { summary, editions });

		expect(screen.getByText('Days').querySelector('span')).toHaveTextContent(/^2$/);
		expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
	});

	it('shows the ranking button once started', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		render(EditionHub, { summary, editions });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('href', '/2026/ranking');
		expect(screen.queryByText('Days')).toBeNull();
	});

	it('shows host, dates, discipline icons and the other editions', () => {
		vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
		render(EditionHub, { summary, editions });

		expect(screen.getByText('Paris · 19 – 20 September 2026')).toBeInTheDocument();
		expect(screen.getByAltText('Relay')).toHaveAttribute('src', expect.stringMatching(/relay\.svg$/));
		expect(screen.getByAltText('Orienteering')).toHaveAttribute('src', expect.stringMatching(/orienteering\.svg$/));
		expect(screen.getByRole('link', { name: '2025' })).toHaveAttribute('href', '/2025');
		expect(screen.getByRole('link', { name: '2024' })).toHaveAttribute('href', '/2024');
		expect(screen.queryByRole('link', { name: '2026' })).toBeNull();
	});

	it('prints one date when the edition lasts a single day', () => {
		vi.setSystemTime(new Date(2026, 8, 19, 10, 0, 0));
		const oneDay = {
			...summary,
			edition: { ...summary.edition, start_date: '2026-09-19', end_date: '2026-09-19' }
		};
		render(EditionHub, { summary: oneDay, editions });

		expect(screen.getByText('Paris · 19 September 2026')).toBeInTheDocument();
	});

	it('ticks and flips to the ranking button when the start passes', async () => {
		vi.setSystemTime(new Date('2026-09-19T06:59:59Z'));
		render(EditionHub, { summary, editions });

		expect(screen.getByText('Seconds').querySelector('span')).toHaveTextContent(/^1$/);

		await vi.advanceTimersByTimeAsync(1000);

		expect(screen.getByRole('link', { name: 'Ranking' })).toBeInTheDocument();
		expect(screen.queryByText('Days')).toBeNull();
	});
});
