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
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*avg 1\.0 over 2 editions\s*100%/);
		expect(rows[1]).toHaveTextContent(/1\s*Hugo Maurinier\s*avg 1\.0 over 1 edition\s*100%/);
		expect(rows[2]).toHaveTextContent(/3\s*Xavier Baby\s*avg 2\.5 over 2 editions\s*76%/);
		expect(rows[0]).toHaveAttribute('href', '/players/12');
	});

	it('medals tied leaders alike, not by row position', () => {
		renderWith(Page, { data });

		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('gold');
		expect(rows[2]).toHaveClass('bronze');
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

	it('has no ranked list when nobody is ranked yet', () => {
		const { container } = renderWith(Page, { data: { players: leaderboard.slice(3) } });

		expect(container.querySelector('ol')).toBeNull();
		expect(screen.queryAllByTestId('player-row')).toHaveLength(0);
		expect(screen.getAllByTestId('unranked-row')).toHaveLength(2);
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Joueurs' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows[2]).toHaveTextContent(/3\s*Xavier Baby\s*moy\. 2,5 sur 2 éditions\s*76\s%/);
		expect(screen.getByRole('heading', { name: 'Pas encore classés' })).toBeInTheDocument();
	});
});
