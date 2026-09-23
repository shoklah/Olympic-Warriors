import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Badge from './Badge.svelte';

describe('Badge', () => {
	it('draws the glyph in a ring of the metal, hidden from assistive tech', () => {
		const { container } = renderWith(Badge, { badge: { code: 'champion', tier: 0, years: [2024] } });
		const root = container.querySelector('[data-metal]');
		expect(root).toHaveAttribute('data-metal', 'gold');
		expect(root).toHaveAttribute('aria-hidden', 'true');
		expect(root.querySelector('img').getAttribute('src')).toMatch(/champion\.svg$/);
		expect(root.querySelector('img')).toHaveAttribute('alt', '');
		expect(root.querySelectorAll('.pip')).toHaveLength(0);
	});

	it('shows three pips for a tiered badge, the first `tier` lit, in the tier metal', () => {
		const { container } = renderWith(Badge, { badge: { code: 'veteran', tier: 2, years: [2026] } });
		expect(container.querySelector('[data-metal]')).toHaveAttribute('data-metal', 'silver');
		expect(container.querySelectorAll('.pip')).toHaveLength(3);
		expect(container.querySelectorAll('.pip.on')).toHaveLength(2);
	});

	it('borrows the discipline icon for a specialist', () => {
		const { container } = renderWith(Badge, {
			badge: { code: 'specialist', tier: 1, years: [2026], discipline: 'Rugby' }
		});
		expect(container.querySelector('img').getAttribute('src')).toMatch(/rugby\.svg$/);
	});
});
