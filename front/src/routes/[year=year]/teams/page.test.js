import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';

describe('teams grid', () => {
	it('lists every team in rank order with its roster', () => {
		render(Page, { data: { summary } });

		const cards = screen.getAllByTestId('team-card');
		expect(cards.map((card) => card.getAttribute('href'))).toEqual([
			'/2026/teams/2',
			'/2026/teams/1',
			'/2026/teams/3'
		]);
		expect(cards[0]).toHaveTextContent('Bisons');
		expect(cards[1]).toHaveTextContent('Aigles');
		expect(cards[2]).toHaveTextContent('Cerfs');
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
	});
});
