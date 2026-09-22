import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';

describe('disciplines grid', () => {
	it('links every discipline of the edition, revealed or not', () => {
		render(Page, { data: { summary } });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveAttribute(
			'href',
			'/2026/disciplines/10'
		);
		expect(screen.getByRole('link', { name: 'Orienteering' })).toHaveAttribute(
			'href',
			'/2026/disciplines/11'
		);
	});

	it('keeps an unrevealed discipline reachable, only its icon dimmed', () => {
		render(Page, { data: { summary } });

		const card = screen.getByRole('link', { name: 'Orienteering' });
		expect(card).not.toHaveClass('dimmed');
		expect(card).not.toHaveAttribute('aria-disabled');
		expect(card).toHaveClass('unrevealed');
	});

	it('subtitles a card with its rounds and games', () => {
		render(Page, { data: { summary } });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveTextContent('2 rounds · 3 games');
	});
});
