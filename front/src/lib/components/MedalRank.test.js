import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import MedalRank from './MedalRank.svelte';

describe('MedalRank', () => {
	it('gives the first three ranks their medal class', () => {
		expect(renderWith(MedalRank, { rank: 1 }).container.querySelector('.gold')).toHaveTextContent('1');
		expect(renderWith(MedalRank, { rank: 2 }).container.querySelector('.silver')).toHaveTextContent(
			'2'
		);
		expect(renderWith(MedalRank, { rank: 3 }).container.querySelector('.bronze')).toHaveTextContent(
			'3'
		);
	});

	it('renders any other rank without a medal', () => {
		const { container } = renderWith(MedalRank, { rank: 4 });

		expect(container.querySelector('.none')).toHaveTextContent('4');
		expect(screen.getByText('4')).toBeInTheDocument();
	});

	it('renders a dash without a rank', () => {
		const { container } = renderWith(MedalRank, { rank: null });

		expect(container.querySelector('.none')).toHaveTextContent('—');
	});

	it('treats rank 0, the unrevealed value, as no rank', () => {
		const { container } = renderWith(MedalRank, { rank: 0 });

		expect(container.querySelector('.none')).toHaveTextContent('—');
		expect(container.querySelector('.none')).not.toHaveTextContent('0');
	});

	it('renders the ordinal when asked', () => {
		const { container } = renderWith(MedalRank, { rank: 2, ordinal: true });

		expect(container.querySelector('.silver')).toHaveTextContent('2nd');
	});

	it('carries the rank class pages size through --medal-size', () => {
		const { container } = renderWith(MedalRank, { rank: 1 });

		expect(container.querySelector('.gold')).toHaveClass('rank');
	});

	it('keeps the medal in ordinal mode', () => {
		const { container } = renderWith(MedalRank, { rank: 1, ordinal: true });

		expect(container.querySelector('.gold')).toHaveTextContent('1st');
	});

	it('keeps the dash in ordinal mode', () => {
		const { container } = renderWith(MedalRank, { rank: null, ordinal: true });

		expect(container.querySelector('.none')).toHaveTextContent('—');
	});

	it('writes the French ordinal under fr', () => {
		expect(renderWith(MedalRank, { rank: 1, ordinal: true }, 'fr').container.querySelector('.gold')).toHaveTextContent('1re');
		expect(renderWith(MedalRank, { rank: 4, ordinal: true }, 'fr').container.querySelector('.none')).toHaveTextContent('4e');
	});
});
