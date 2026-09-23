import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';
import { renderWith } from '$lib/test-utils';

describe('ranking page', () => {
	it('lists teams in rank order with total points', () => {
		renderWith(Page, { data: { summary } });

		const rows = screen.getAllByTestId('team-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\s*Bisons\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/2\s*Aigles\s*3 pts/);
		expect(rows[2]).toHaveTextContent(/3\s*Cerfs\s*2 pts/);
		// the whole row is the link
		expect(rows[0]).toHaveAttribute('href', '/2026/teams/2');
	});

	it('medals the top three by rank, not by row position', () => {
		renderWith(Page, { data: { summary } });

		const rows = screen.getAllByTestId('team-row');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('silver');
		expect(rows[2]).toHaveClass('bronze');
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
		expect(screen.getAllByTestId('team-row')[0]).toHaveTextContent(/1\s*Bisons\s*5 pts/);
	});
});
