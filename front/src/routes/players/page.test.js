import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { leaderboard } from '$lib/fixtures/players.js';

const data = { players: leaderboard };

describe('players leaderboard page', () => {
	it('ranks players by share beaten, ties sharing a position', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { level: 1, name: 'Players' })).toBeInTheDocument();
		expect(screen.getByText('All editions, by share of teams beaten')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*100%\s*avg 1\.0 · 2 editions/);
		expect(rows[1]).toHaveTextContent(/1\s*Hugo Maurinier\s*100%\s*avg 1\.0 · 1 edition/);
		expect(rows[2]).toHaveTextContent(/3\s*Xavier Baby\s*76%\s*avg 2\.5 · 2 editions/);
		expect(rows[0]).toHaveAttribute('href', '/players/12');
	});

	it('lists the players not ranked yet by name, with their editions and no position', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { name: 'Not ranked yet' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('unranked-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/Ana Petit\s*1 edition/);
		expect(rows[1]).toHaveTextContent(/Jules Roux\s*2 editions/);
		expect(rows[1]).toHaveAttribute('href', '/players/41');
	});

	it('has no not-ranked section when everyone is ranked', () => {
		renderWith(Page, { data: { players: leaderboard.slice(0, 3) } });

		expect(screen.queryByRole('heading', { name: 'Not ranked yet' })).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Joueurs' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows[2]).toHaveTextContent(/3\s*Xavier Baby\s*76\s%\s*moy\. 2,5 · 2 éditions/);
		expect(screen.getByRole('heading', { name: 'Pas encore classés' })).toBeInTheDocument();
	});
});
