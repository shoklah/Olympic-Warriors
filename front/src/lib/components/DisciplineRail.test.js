import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DisciplineRail from './DisciplineRail.svelte';
import { summary } from '$lib/fixtures/summary.js';

describe('DisciplineRail', () => {
	it('links revealed disciplines and disables hidden ones', () => {
		render(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: null });

		expect(screen.getByRole('navigation', { name: 'Disciplines' })).toBeInTheDocument();

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('href', '/2026/disciplines/10');
		expect(relay).not.toHaveAttribute('aria-disabled');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).toHaveAttribute('aria-disabled', 'true');
		expect(orienteering).toHaveAttribute('tabindex', '-1');
		expect(orienteering).toHaveClass('dimmed');
	});

	it('marks the current discipline and nothing else', () => {
		render(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: 10 });

		const relay = screen.getByRole('link', { name: 'Relay' });
		expect(relay).toHaveAttribute('aria-current', 'page');
		expect(relay).toHaveClass('current');

		const orienteering = screen.getByRole('link', { name: 'Orienteering' });
		expect(orienteering).not.toHaveAttribute('aria-current');
		expect(orienteering).not.toHaveClass('current');
	});

	it('marks nothing without a current discipline', () => {
		render(DisciplineRail, { year: 2026, disciplines: summary.disciplines });

		expect(screen.getByRole('link', { name: 'Relay' })).not.toHaveAttribute('aria-current');
	});
});
