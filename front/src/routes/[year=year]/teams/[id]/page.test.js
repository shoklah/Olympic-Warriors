import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { load } from './+page.js';
import { findTeam, teamGames, teamResults } from '$lib/edition';
import { summary } from '$lib/fixtures/summary.js';

const dataFor = (id) => ({
	summary,
	team: findTeam(summary, id),
	results: teamResults(summary, id),
	games: teamGames(summary, id)
});

describe('team page', () => {
	it('shows the name, global rank, total points and the full roster', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Aigles' })).toBeInTheDocument();
		expect(screen.getByTestId('standing')).toHaveTextContent(/2nd\s*overall\s*3\s*pts/);
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
		expect(screen.getByText('Bob Martin')).toBeInTheDocument();
	});

	it('shows one tile per discipline with a dash when not revealed', () => {
		renderWith(Page, { data: dataFor(1) });

		const rows = screen.getAllByTestId('discipline-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/Relay\s*2nd\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/Orienteering\s*—/);
	});

	it('lists games per discipline with result, to play and referee rows', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Games' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('game-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/Round 1 · vs Bisons · 9 : 12 · lost/);
		expect(rows[1]).toHaveTextContent(/Round 1 · referee · Cerfs vs Bisons/);
		expect(rows[2]).toHaveTextContent(/Round 2 · vs Cerfs · 7 : 7 · draw/);
		expect(rows[3]).toHaveTextContent(/Round 1 · vs Bisons · played/);
	});

	it('says to play for an unplayed game', () => {
		renderWith(Page, { data: dataFor(2) });
		expect(screen.getAllByTestId('game-row')[1]).toHaveTextContent(/Round 1 · vs Cerfs · to play/);
		expect(screen.getAllByTestId('game-row')[0]).toHaveTextContent(
			/Round 1 · vs Aigles · 12 : 9 · won/
		);
	});

	it('has no games section when the team has no games', () => {
		renderWith(Page, { data: { ...dataFor(1), games: [] } });
		expect(screen.queryByRole('heading', { name: 'Games' })).toBeNull();
	});
});

describe('team page load', () => {
	it('404s on an id that matches no team', async () => {
		await expect(
			load({ params: { id: 'abc' }, parent: async () => ({ summary }) })
		).rejects.toMatchObject({ status: 404 });
	});
});
