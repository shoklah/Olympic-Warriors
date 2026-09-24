import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import PlaceList from './PlaceList.svelte';
import { renderWith } from '$lib/test-utils';

const places = [
	{ year: 2025, rank: 1 },
	{ year: 2024, rank: 2 },
	{ year: 2023, rank: 3 },
	{ year: 2022, rank: 5 }
];

describe('PlaceList', () => {
	it('shows each rank with its year, hidden from screen readers behind a sentence', () => {
		const { container } = renderWith(PlaceList, { places });

		const figures = container.querySelector('.places');
		expect(figures).toHaveTextContent(/^1\s*2025\s*2\s*2024\s*3\s*2023\s*5\s*2022$/);
		expect(figures).toHaveAttribute('aria-hidden', 'true');
		expect(
			screen.getByText('1st place in 2025, 2nd place in 2024, 3rd place in 2023, 5th place in 2022')
		).toHaveClass('visually-hidden');
	});

	// Class assertions on purpose here: colour (not text shape) is what's under test.
	it('colours the podium ranks gold, silver and bronze, and nothing after', () => {
		const { container } = renderWith(PlaceList, { places });

		const ranks = container.querySelectorAll('.place-rank');
		expect(ranks[0]).toHaveClass('gold');
		expect(ranks[1]).toHaveClass('silver');
		expect(ranks[2]).toHaveClass('bronze');
		expect(ranks[3]).not.toHaveClass('gold', 'silver', 'bronze');
	});

	it('speaks French without a locale in context', () => {
		render(PlaceList, { props: { places: places.slice(0, 2) } });

		expect(screen.getByText('1re place en 2025, 2e place en 2024')).toBeInTheDocument();
	});
});
