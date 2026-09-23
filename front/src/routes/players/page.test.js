import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { leaderboard } from '$lib/fixtures/players.js';

const data = { players: leaderboard };
const ranked = leaderboard.filter((p) => p.position !== null);
const waiting = leaderboard.filter((p) => p.position === null);

describe('players leaderboard page', () => {
	it('ranks players by their places, best first, with a spoken sentence', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { level: 1, name: 'Players' })).toBeInTheDocument();
		expect(screen.getByText('Ranked by 1st places, then 2nd, then 3rd…')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*1\s*2\s*1st place in 2024, 2nd place in 2026/);
		expect(rows[1]).toHaveTextContent(/2\s*Hugo Maurinier\s*1\s*1st place in 2025/);
		expect(rows[2]).toHaveTextContent(/2\s*Inès Moreau\s*1\s*1st place in 2025/);
		expect(rows[3]).toHaveTextContent(/4\s*Xavier Baby\s*2\s*3\s*2nd place in 2026, 3rd place in 2023/);
		expect(rows[0]).toHaveAttribute('href', '/players/12');
		expect(within(rows[0]).getByTestId('places')).toHaveAttribute('aria-hidden', 'true');
		expect(rows[0]).not.toHaveTextContent(/%|avg/);
	});

	it('colours each place like a medal', () => {
		renderWith(Page, { data });

		const places = within(screen.getAllByTestId('player-row')[3]).getByTestId('places');
		const [second, third] = places.querySelectorAll('.place');
		expect(second).toHaveClass('silver');
		expect(third).toHaveClass('bronze');
	});

	it('medals tied players alike, not by row position', () => {
		renderWith(Page, { data });

		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('silver');
		expect(rows[2]).toHaveClass('silver');
		expect(rows[3]).not.toHaveClass('bronze');
	});

	it('shows the best places only past the cap, with the rest counted', () => {
		const places = Array.from({ length: 10 }, (_, i) => ({ year: 2030 - i, rank: 1 + (i % 3) }));
		const busy = { ...ranked[0], places };
		renderWith(Page, { data: { players: [busy] } });

		const row = screen.getByTestId('player-row');
		expect(within(row).getByTestId('places').querySelectorAll('.place')).toHaveLength(8);
		expect(within(row).getByTestId('places')).toHaveTextContent('+2');
		// The spoken sentence still lists all ten.
		expect(row.textContent.match(/place in/g)).toHaveLength(10);
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
		renderWith(Page, { data: { players: ranked } });

		expect(screen.queryByRole('heading', { name: 'Not ranked yet' })).toBeNull();
	});

	it('has no ranked list when nobody is ranked yet', () => {
		const { container } = renderWith(Page, { data: { players: waiting } });

		expect(container.querySelector('ol')).toBeNull();
		expect(screen.queryAllByTestId('player-row')).toHaveLength(0);
		expect(screen.getAllByTestId('unranked-row')).toHaveLength(2);
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Joueurs' })).toBeInTheDocument();
		expect(screen.getByText('Classés par nombre de 1res places, puis de 2es, puis de 3es…')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveTextContent(/1\s*Léa Martin\s*1\s*2\s*1re place en 2024, 2e place en 2026/);
		expect(screen.getByRole('heading', { name: 'Pas encore classés' })).toBeInTheDocument();
	});
});
