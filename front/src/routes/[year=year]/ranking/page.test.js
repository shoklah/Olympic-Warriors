import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';

describe('ranking page', () => {
	it('lists teams in rank order with total points', () => {
		render(Page, { data: { summary } });

		const rows = screen.getAllByTestId('team-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\. Bisons\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/2\. Aigles\s*3 pts/);
		expect(rows[2]).toHaveTextContent(/3\. Cerfs\s*2 pts/);
		expect(within(rows[0]).getByRole('link')).toHaveAttribute('href', '/2026/teams/2');
	});

	it('links revealed disciplines and disables hidden ones', () => {
		render(Page, { data: { summary } });

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('href', '/2026/disciplines/10');
		expect(relay).not.toHaveAttribute('aria-disabled');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).toHaveAttribute('aria-disabled', 'true');
	});
});
