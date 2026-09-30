import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Badge from './Badge.svelte';

// Vitest runs from the front root, and component styles are not loaded under jsdom: the
// sizes are read from the sources.
const source = (path) => readFileSync(path, 'utf8');
/** Every `.svelte` file of the tree, as [path, source]. */
const components = () =>
	readdirSync('src', { recursive: true })
		.map((path) => path.replaceAll('\\', '/'))
		.filter((path) => path.endsWith('.svelte'))
		.map((path) => [path, source(`src/${path}`)]);

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

	// A larger default font size (a browser or system setting) grows the text: a medallion
	// in rem grows with it, one in px would end up tiny beside the name.
	it('is sized in rem, so it follows the default font size: 3.5rem, pips at least 0.3125rem', () => {
		const css = source('src/lib/components/Badge.svelte');
		expect(css).toMatch(/--size: var\(--badge-size, 3\.5rem\);/);
		expect(css).toMatch(/--pip: max\(0\.3125rem, calc\(var\(--size\) \* 0\.07\)\);/);
	});

	it('is scaled in rem wherever a page or a component sets --badge-size', () => {
		// A declaration (`--badge-size: 3rem;`, in a style block or attribute) or a
		// `style:--badge-size="…"` directive; `var(--badge-size…)` reads it and is left out.
		const sizes = components().flatMap(([path, text]) =>
			[...text.matchAll(/--badge-size(?::\s*|=")([^;"}]+)/g)].map((m) => [path, m[1].trim()])
		);
		expect(sizes.length).toBeGreaterThan(0);
		for (const [path, size] of sizes) {
			expect(size, path).toMatch(/^\d+(\.\d+)?rem$/);
		}
	});
});
