import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';

describe('teams grid', () => {
	it('lists every team in name order with its roster', () => {
		render(Page, { data: { summary } });

		const links = screen.getAllByRole('link');
		expect(links.map((link) => link.getAttribute('href'))).toEqual([
			'/2026/teams/1',
			'/2026/teams/2',
			'/2026/teams/3'
		]);
		expect(links[0]).toHaveTextContent('Aigles');
		expect(links[1]).toHaveTextContent('Bisons');
		expect(links[2]).toHaveTextContent('Cerfs');
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
	});
});
