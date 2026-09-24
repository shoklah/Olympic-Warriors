import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import AllTimeTable from './AllTimeTable.svelte';
import { allTime, allTimeEmpty } from '$lib/fixtures/players.js';
import { renderWith } from '$lib/test-utils';

describe('AllTimeTable', () => {
	it('lists every person with their shared position, name and places', () => {
		renderWith(AllTimeTable, { table: allTime });

		const rows = screen.getAllByTestId('all-time-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/^1\s*Léa Martin\s*1\s*2025\s*2\s*2024/);
		expect(rows[1]).toHaveTextContent(/^1\s*Hugo Maurinier\s*1\s*2024\s*2\s*2025/);
		expect(rows[2]).toHaveTextContent(/^3\s*Inès Moreau\s*1\s*2025/);
		expect(rows[3]).toHaveTextContent(/^4\s*Xavier Baby\s*4\s*2024/);
	});

	it('links each row to the profile, named by position, name and spoken places', () => {
		renderWith(AllTimeTable, { table: allTime });

		const lea = screen.getByRole('link', { name: '1 Léa Martin 1st place in 2025, 2nd place in 2024' });
		expect(lea).toHaveAttribute('href', '/players/12');
		expect(lea.querySelector('.places')).toHaveAttribute('aria-hidden', 'true');
	});

	// Class assertions on purpose here: colour (not text shape) is what's under test.
	it('marks the podium positions and colours the podium places', () => {
		renderWith(AllTimeTable, { table: allTime });

		const rows = screen.getAllByTestId('all-time-row');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('gold');
		expect(rows[2]).toHaveClass('bronze');
		expect(rows[3]).not.toHaveClass('gold', 'silver', 'bronze');
		const ranks = rows[0].querySelectorAll('.place-rank');
		expect(ranks[0]).toHaveClass('gold');
		expect(ranks[1]).toHaveClass('silver');
		expect(rows[3].querySelector('.place-rank')).not.toHaveClass('gold', 'silver', 'bronze');
	});

	it('names the editions it covers, one or several', () => {
		const { unmount } = renderWith(AllTimeTable, { table: allTime });
		expect(screen.getByText('2024 and 2025 editions')).toBeInTheDocument();
		unmount();

		renderWith(AllTimeTable, { table: { ...allTime, years: [2024] } });
		expect(screen.getByText('2024 edition')).toBeInTheDocument();
	});

	it('has a hidden heading for the section', () => {
		renderWith(AllTimeTable, { table: allTime });

		expect(screen.getByRole('heading', { level: 2, name: 'All time' })).toHaveClass('visually-hidden');
	});

	it('says so when no finished edition placed anyone', () => {
		renderWith(AllTimeTable, { table: allTimeEmpty });

		expect(screen.getByText('No finished edition for this discipline yet')).toBeInTheDocument();
		expect(screen.queryAllByTestId('all-time-row')).toHaveLength(0);
		expect(screen.queryByText(/edition$/)).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(AllTimeTable, { table: { ...allTime, years: [2024, 2025, 2026] } }, 'fr');

		expect(screen.getByRole('heading', { level: 2, name: 'Palmarès' })).toBeInTheDocument();
		expect(screen.getByText('Éditions 2024, 2025 et 2026')).toBeInTheDocument();
		const rows = screen.getAllByTestId('all-time-row');
		expect(within(rows[0]).getByText('1re place en 2025, 2e place en 2024')).toBeInTheDocument();
	});

	it('words the empty state in French under fr', () => {
		renderWith(AllTimeTable, { table: allTimeEmpty }, 'fr');

		expect(screen.getByText('Aucune édition terminée pour cette épreuve')).toBeInTheDocument();
	});
});
