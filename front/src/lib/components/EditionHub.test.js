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

		expect(screen.getByText('Days').querySelector('span')).toHaveTextContent('2');
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

		expect(screen.getByText(/Paris/)).toBeInTheDocument();
		expect(screen.getByAltText('Relay')).toHaveAttribute('src', expect.stringMatching(/relay\.svg|default\.svg/));
		expect(screen.getByAltText('Orienteering')).toHaveAttribute('src', expect.stringMatching(/orienteering\.svg$/));
		expect(screen.getByRole('link', { name: '2025' })).toHaveAttribute('href', '/2025');
		expect(screen.getByRole('link', { name: '2024' })).toHaveAttribute('href', '/2024');
		expect(screen.queryByRole('link', { name: '2026' })).toBeNull();
	});
});
