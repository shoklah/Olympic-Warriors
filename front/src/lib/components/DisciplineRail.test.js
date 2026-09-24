import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DisciplineRail from './DisciplineRail.svelte';
import { summary } from '$lib/fixtures/summary.js';
import { renderWith } from '$lib/test-utils';

describe('DisciplineRail', () => {
	it('links revealed disciplines and disables hidden ones', () => {
		renderWith(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: null });

		expect(screen.getByRole('navigation', { name: 'Disciplines' })).toBeInTheDocument();

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('href', '/2026/disciplines/10');
		expect(relay).not.toHaveAttribute('aria-disabled');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).toHaveAttribute('href', '/2026/disciplines/11');
		expect(orienteering).not.toHaveAttribute('aria-disabled');
		expect(orienteering).not.toHaveAttribute('tabindex');
		expect(orienteering).toHaveClass('unrevealed');
	});

	it('marks the current discipline and nothing else', () => {
		renderWith(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: 10 });

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('aria-current', 'page');
		expect(relay).toHaveClass('current');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).not.toHaveAttribute('aria-current');
		expect(orienteering).not.toHaveClass('current');
	});

	it('marks nothing without a current discipline', () => {
		renderWith(DisciplineRail, { year: 2026, disciplines: summary.disciplines });

		expect(screen.getByRole('link', { name: 'Relay' })).not.toHaveAttribute('aria-current');
	});

	it('keeps the discipline page tab it is given', () => {
		renderWith(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: 10, tab: 'all-time' });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveAttribute('href', '/2026/disciplines/10?tab=all-time');
		expect(screen.getByRole('link', { name: 'Orienteering' })).toHaveAttribute(
			'href',
			'/2026/disciplines/11?tab=all-time'
		);
	});

	it('names the tiles in French under fr', () => {
		renderWith(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: null }, 'fr');

		expect(screen.getByRole('navigation', { name: 'Épreuves' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Relais' })).toHaveAttribute('href', '/2026/disciplines/10');
	});
});
