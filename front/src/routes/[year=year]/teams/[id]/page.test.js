import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { load } from './+page.js';
import { findTeam, teamResults } from '$lib/edition';
import { summary } from '$lib/fixtures/summary.js';

const dataFor = (id) => ({ summary, team: findTeam(summary, id), results: teamResults(summary, id) });

describe('team page', () => {
	it('shows the name, global rank, total points and the full roster', () => {
		render(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Aigles' })).toBeInTheDocument();
		expect(screen.getByText('2nd · 3 pts')).toBeInTheDocument();
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
		expect(screen.getByText('Bob Martin')).toBeInTheDocument();
	});

	it('shows one row per discipline with a dash when not revealed', () => {
		render(Page, { data: dataFor(1) });

		const rows = screen.getAllByTestId('discipline-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/Relay\s*2\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/Orienteering\s*—\s*—/);
	});
});

describe('team page load', () => {
	it('404s on an id that matches no team', async () => {
		await expect(
			load({ params: { id: 'abc' }, parent: async () => ({ summary }) })
		).rejects.toMatchObject({ status: 404 });
	});
});
