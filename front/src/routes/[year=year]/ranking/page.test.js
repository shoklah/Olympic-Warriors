import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';
import { renderWith } from '$lib/test-utils';

describe('ranking page', () => {
	it('lists teams in rank order with their roster and total points', () => {
		renderWith(Page, { data: { summary } });

		const cards = screen.getAllByTestId('team-card');
		expect(cards).toHaveLength(3);
		expect(cards[0]).toHaveTextContent(/1\s*Bisons\s*Chloé Nguyen\s*5 pts/);
		expect(cards[1]).toHaveTextContent(/2\s*Aigles\s*Ana Lopez · Bob Martin\s*3 pts/);
		expect(cards[2]).toHaveTextContent(/3\s*Cerfs\s*2 pts/);
		// the whole card is the link
		expect(cards.map((card) => card.getAttribute('href'))).toEqual([
			'/2026/teams/2',
			'/2026/teams/1',
			'/2026/teams/3'
		]);
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
	});

	it('medals the top three by rank, not by row position', () => {
		renderWith(Page, { data: { summary } });

		const cards = screen.getAllByTestId('team-card');
		expect(cards[0]).toHaveClass('gold');
		expect(cards[1]).toHaveClass('silver');
		expect(cards[2]).toHaveClass('bronze');
	});

	it('links every discipline and dims the hidden ones', () => {
		renderWith(Page, { data: { summary } });

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('href', '/2026/disciplines/10');
		expect(relay).not.toHaveAttribute('aria-disabled');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).toHaveAttribute('href', '/2026/disciplines/11');
		expect(orienteering).not.toHaveAttribute('aria-disabled');
		expect(orienteering).toHaveClass('unrevealed');
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: { summary } }, 'fr');

		expect(screen.getByRole('heading', { name: 'Classement' })).toBeInTheDocument();
		expect(screen.getByRole('navigation', { name: 'Épreuves' })).toBeInTheDocument();
		expect(screen.getAllByTestId('team-card')[0]).toHaveTextContent(/1\s*Bisons\s*Chloé Nguyen\s*5 pts/);
	});
});
