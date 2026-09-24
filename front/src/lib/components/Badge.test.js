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

	it('keeps an empty pip row on an untiered badge, so medallions in a grid line up', () => {
		const { container } = renderWith(Badge, { badge: { code: 'rookie', tier: 0, years: [2024] } });
		const root = container.querySelector('[data-metal]');
		expect(root.lastElementChild).toHaveClass('pips');
		expect(root.lastElementChild).toBeEmptyDOMElement();
	});

	it('shows three pips for a tiered badge, the first `tier` lit, in the tier metal', () => {
		const { container } = renderWith(Badge, { badge: { code: 'veteran', tier: 2, years: [2026] } });
		expect(container.querySelector('[data-metal]')).toHaveAttribute('data-metal', 'silver');
		const lit = [...container.querySelectorAll('.pip')].map((pip) => pip.classList.contains('on'));
		expect(lit).toEqual([true, true, false]);
	});

	it('lights the pips of the clamped tier, matching the metal', () => {
		const lit = (tier) => {
			const { container } = renderWith(Badge, { badge: { code: 'veteran', tier, years: [2026] } });
			return [
				container.querySelector('[data-metal]').getAttribute('data-metal'),
				[...container.querySelectorAll('.pip')].map((pip) => pip.classList.contains('on'))
			];
		};
		expect(lit(0)).toEqual(['bronze', [true, false, false]]);
		expect(lit(4)).toEqual(['gold', [true, true, true]]);
		expect(lit(undefined)).toEqual(['bronze', [true, false, false]]);
	});

	it('borrows the discipline icon for a specialist', () => {
		const { container } = renderWith(Badge, {
			badge: { code: 'specialist', tier: 1, years: [2026], discipline: 'Rugby' }
		});
		expect(container.querySelector('img').getAttribute('src')).toMatch(/rugby\.svg$/);
	});

	it('draws a locked medallion with a dashed ring and no lit pip', () => {
		const { container } = renderWith(Badge, { badge: { code: 'veteran', tier: 0, years: [] }, locked: true });
		const root = container.querySelector('.badge');
		expect(root).toHaveClass('locked');
		expect(root.querySelectorAll('.pip.on')).toHaveLength(0);
	});

	it('carries no metal on a locked medallion: it has not been earned', () => {
		const { container } = renderWith(Badge, { badge: { code: 'champion', tier: 0, years: [] }, locked: true });
		const root = container.querySelector('.badge');
		expect(root).not.toHaveAttribute('data-metal');
		expect(root).not.toHaveClass('gold');
	});
});
