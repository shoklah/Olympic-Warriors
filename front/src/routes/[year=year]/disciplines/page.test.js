import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { summary } from '$lib/fixtures/summary.js';
import { held } from '$lib/fixtures/held.js';

describe('disciplines grid', () => {
	it('links every discipline of the edition, revealed or not', () => {
		renderWith(Page, { data: { summary } });

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
		renderWith(Page, { data: { summary } });

		const card = screen.getByRole('link', { name: 'Orienteering' });
		expect(card).not.toHaveClass('dimmed');
		expect(card).not.toHaveAttribute('aria-disabled');
		expect(card).toHaveClass('unrevealed');
	});

	it('subtitles a card with its rounds and games', () => {
		renderWith(Page, { data: { summary } });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveTextContent('2 rounds · 3 games');
	});

	it('names and subtitles the cards in French under fr', () => {
		renderWith(Page, { data: { summary } }, 'fr');

		expect(screen.getByRole('heading', { name: 'Épreuves' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Relais' })).toHaveTextContent('2 tours · 3 matchs');
		expect(screen.getByRole('link', { name: "Course d'orientation" })).toHaveTextContent('1 tour · 1 match');
	});

	it('lists every discipline ever held below, each leading to its all-time table', () => {
		renderWith(Page, { data: { summary, held } });

		expect(screen.getByRole('heading', { level: 2, name: 'All time' })).toBeInTheDocument();
		expect(screen.getAllByTestId('all-time-card').map((card) => card.getAttribute('aria-label'))).toEqual([
			'Blindtest, all time',
			'Dodgeball, all time',
			'Hide and Seek, all time',
			'Relay, all time'
		]);
		expect(screen.getByRole('link', { name: 'Relay, all time' })).toHaveTextContent(
			'Relay 3 editions · 2023–2026'
		);
		expect(screen.getByRole('link', { name: 'Hide and Seek, all time' })).toHaveTextContent(
			'Hide and Seek 1 edition · 2026'
		);
	});

	it("leads to the all-time tab of this year's page when this edition held it, else of the newest", () => {
		renderWith(Page, { data: { summary, held } });

		// The summary fixture is 2026, whose Relay is id 10.
		expect(screen.getByRole('link', { name: 'Relay, all time' })).toHaveAttribute(
			'href',
			'/2026/disciplines/10?tab=all-time'
		);
		expect(screen.getByRole('link', { name: 'Blindtest, all time' })).toHaveAttribute(
			'href',
			'/2025/disciplines/31?tab=all-time'
		);
	});

	it("keeps this edition's cards first and named by the discipline alone", () => {
		renderWith(Page, { data: { summary, held } });

		const links = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
		expect(links.indexOf('/2026/disciplines/10')).toBeLessThan(links.indexOf('/2026/disciplines/10?tab=all-time'));
		expect(screen.getByRole('link', { name: 'Relay' })).toHaveAttribute('href', '/2026/disciplines/10');
	});

	it('shows no all-time section when nothing was ever held', () => {
		renderWith(Page, { data: { summary, held: [] } });

		expect(screen.queryByRole('heading', { level: 2 })).toBeNull();
		expect(screen.queryAllByTestId('all-time-card')).toHaveLength(0);
	});

	it('names and orders the all-time cards in French under fr', () => {
		renderWith(Page, { data: { summary, held } }, 'fr');

		expect(screen.getByRole('heading', { level: 2, name: 'Palmarès' })).toBeInTheDocument();
		expect(screen.getAllByTestId('all-time-card').map((card) => card.getAttribute('aria-label'))).toEqual([
			'Balle au prisonnier, palmarès',
			'Blindtest, palmarès',
			'Cache-cache, palmarès',
			'Relais, palmarès'
		]);
		expect(screen.getByRole('link', { name: 'Relais, palmarès' })).toHaveTextContent('Relais 3 éditions · 2023–2026');
		expect(screen.getByRole('link', { name: 'Balle au prisonnier, palmarès' })).toHaveTextContent(
			'Balle au prisonnier 1 édition · 2025'
		);
	});
});
