import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { load } from './+page.js';
import { findTeam, teamGames, teamResults } from '$lib/edition';
import { summary, summaryAllRevealed, summaryManual } from '$lib/fixtures/summary.js';

const dataFor = (id, s = summary) => ({
	summary: s,
	team: findTeam(s, id),
	results: teamResults(s, id),
	games: teamGames(s, id)
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

	it('lists the games the team played as discipline-page rows with the own team highlighted', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Games' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('game-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/R1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(rows[0]).toHaveTextContent('ref: Cerfs');
		expect(rows[1]).toHaveTextContent(/R2\s*Aigles\s*7 : 7\s*Cerfs/);
		expect(rows[2]).toHaveTextContent(/R1\s*Aigles\s*played\s*Bisons/);

		expect(within(rows[0]).getByText('Aigles')).toHaveClass('own');
		expect(within(rows[0]).getByText('Aigles')).toHaveClass('loser');
		expect(within(rows[0]).queryByRole('link', { name: 'Aigles' })).toBeNull();
		expect(within(rows[0]).getByRole('link', { name: 'Bisons' })).toHaveAttribute('href', '/2026/teams/2');
	});

	it('dashes an unplayed game and lists no refereed game', () => {
		renderWith(Page, { data: dataFor(2) });

		const rows = screen.getAllByTestId('game-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/R1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(rows[1]).toHaveTextContent(/R1\s*Cerfs\s*— : —\s*Bisons/);
		// Game 203 (Orienteering) is the third row; the refereed Relay game of Aigles never shows for Bisons.
		expect(rows[2]).toHaveTextContent(/R1\s*Aigles\s*played\s*Bisons/);
	});

	it('shows a revealed timed result as mm:ss', () => {
		renderWith(Page, { data: dataFor(1, summaryAllRevealed) });

		const rows = screen.getAllByTestId('discipline-row');
		expect(rows[1]).toHaveTextContent(/Orienteering\s*1st\s*12:30/);
	});

	it('has no games section when the team has no games', () => {
		renderWith(Page, { data: { ...dataFor(1), games: [] } });
		expect(screen.queryByRole('heading', { name: 'Games' })).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: dataFor(2) }, 'fr');

		expect(screen.getByTestId('standing')).toHaveTextContent(/1re\s*au général\s*5\s*pts/);
		expect(screen.getByRole('heading', { name: 'Matchs' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Relais' })).toBeInTheDocument();
		expect(screen.getAllByTestId('game-row')[0]).toHaveTextContent(/T1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(screen.getAllByTestId('discipline-row')[1]).toHaveTextContent(/Course d'orientation\s*—\s*non dévoilé/);
	});

	it('shows the rank alone on a hand-ranked edition', () => {
		renderWith(Page, { data: dataFor(1, summaryManual) });

		expect(screen.getByTestId('standing')).toHaveTextContent(/^\s*2nd\s*overall\s*$/);
	});

	it('shows a dash for a team without a rank, in French too', () => {
		renderWith(Page, { data: dataFor(3, summaryManual) }, 'fr');

		expect(screen.getByTestId('standing')).toHaveTextContent(/^\s*—\s*au général\s*$/);
		expect(screen.queryByText('pts')).not.toBeInTheDocument();
	});

	it('links each roster name to the player profile', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('link', { name: 'Ana Lopez' })).toHaveAttribute('href', '/players/11');
		expect(screen.getByRole('link', { name: 'Bob Martin' })).toHaveAttribute('href', '/players/12');
	});
});

describe('team page load', () => {
	it('404s on an id that matches no team', async () => {
		await expect(
			load({ params: { id: 'abc' }, parent: async () => ({ summary }) })
		).rejects.toMatchObject({ status: 404 });
	});
});
