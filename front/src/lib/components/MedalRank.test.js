import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import MedalRank from './MedalRank.svelte';

describe('MedalRank', () => {
	it('gives the first three ranks their medal class', () => {
		expect(render(MedalRank, { rank: 1 }).container.querySelector('.gold')).toHaveTextContent('1');
		expect(render(MedalRank, { rank: 2 }).container.querySelector('.silver')).toHaveTextContent(
			'2'
		);
		expect(render(MedalRank, { rank: 3 }).container.querySelector('.bronze')).toHaveTextContent(
			'3'
		);
	});

	it('renders any other rank without a medal', () => {
		const { container } = render(MedalRank, { rank: 4 });

		expect(container.querySelector('.none')).toHaveTextContent('4');
		expect(screen.getByText('4')).toBeInTheDocument();
	});

	it('renders a dash without a rank', () => {
		const { container } = render(MedalRank, { rank: null });

		expect(container.querySelector('.none')).toHaveTextContent('—');
	});

	it('renders the ordinal when asked', () => {
		const { container } = render(MedalRank, { rank: 2, ordinal: true });

		expect(container.querySelector('.silver')).toHaveTextContent('2nd');
	});

	it('keeps the dash in ordinal mode', () => {
		const { container } = render(MedalRank, { rank: null, ordinal: true });

		expect(container.querySelector('.none')).toHaveTextContent('—');
	});
});
