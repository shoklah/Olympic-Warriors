import { fireEvent, screen, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { badgeCollection } from '$lib/badges';
import { leaderboard, profile } from '$lib/fixtures/players.js';
import Showcase from './Showcase.svelte';

const collection = badgeCollection(profile.badges);
/** Pinned out of catalogue order (comrades, specialist, clean sweep), so the order shown
    can only be the pin order. */
const pinned = [
	{ code: 'specialist', tier: 1, discipline: 'Relay' },
	{ code: 'comrades', tier: 0, discipline: null },
	{ code: 'clean-sweep', tier: 0, discipline: null }
];
const unknown = { code: 'future-badge', tier: 0, discipline: null };

const glyphs = (root) => [...root.querySelectorAll('img')].map((img) => img.getAttribute('src'));

afterEach(() => {
	document.body.style.overflow = '';
});

describe('Showcase on a leaderboard row', () => {
	it('draws the medallions in pin order, hidden from assistive tech, at 20px, with nothing to press', () => {
		renderWith(Showcase, { badges: leaderboard[0].showcase });

		const root = screen.getByTestId('showcase');
		expect(root).toHaveAttribute('aria-hidden', 'true');
		expect(root.style.getPropertyValue('--badge-size')).toBe('20px');
		expect(glyphs(root)).toEqual([
			expect.stringMatching(/champion\.svg$/),
			expect.stringMatching(/veteran\.svg$/),
			expect.stringMatching(/networker\.svg$/)
		]);
		// Drawn from each entry: champion's gold, then veteran at tier 2 and networker at tier 1.
		expect([...root.querySelectorAll('[data-metal]')].map((el) => el.dataset.metal)).toEqual([
			'gold',
			'silver',
			'bronze'
		]);
		expect(screen.queryAllByRole('button')).toHaveLength(0);
	});

	it("draws a specialist with its discipline's icon", () => {
		renderWith(Showcase, { badges: [pinned[0]] });

		expect(glyphs(screen.getByTestId('showcase'))).toEqual([expect.stringMatching(/relay\.svg$/)]);
	});

	it('leaves out a code the front does not know', () => {
		renderWith(Showcase, { badges: [unknown, ...leaderboard[0].showcase.slice(0, 1)] });

		expect(glyphs(screen.getByTestId('showcase'))).toEqual([expect.stringMatching(/champion\.svg$/)]);
	});

	it('renders nothing at all for a person without a badge, not even an empty line', () => {
		for (const badges of [[], [unknown], undefined]) {
			const { container } = renderWith(Showcase, { badges });
			expect(container.querySelector('*')).toBeNull();
		}
	});
});

describe('Showcase in the profile header', () => {
	const renderHeader = (props = {}, locale = 'en') =>
		renderWith(Showcase, { badges: pinned, mode: 'interactive', collection, ...props }, locale);

	it('gives each medallion a button, in pin order, named like the collection slots', () => {
		renderHeader();

		const list = screen.getByRole('list', { name: 'Showcase' });
		const buttons = within(list).getAllByRole('button');
		expect(buttons.map((b) => b.getAttribute('aria-label'))).toEqual([
			'Specialist, badge earned',
			'Comrades in arms, badge earned',
			'Clean sweep, badge earned 2 times'
		]);
		expect(glyphs(list)).toEqual([
			expect.stringMatching(/relay\.svg$/),
			expect.stringMatching(/comrades\.svg$/),
			expect.stringMatching(/clean-sweep\.svg$/)
		]);
	});

	it("opens the badge's sheet, with the rarity from badge_stats, and gives focus back on close", async () => {
		renderHeader({ badgeStats: profile.badge_stats });

		const button = screen.getByRole('button', { name: 'Comrades in arms, badge earned' });
		await fireEvent.click(button);
		const dialog = screen.getByRole('dialog', { name: 'Comrades in arms' });
		expect(dialog).toHaveTextContent('17% of players have it (8 of 47)');
		expect(within(dialog).getByRole('link', { name: 'Léa Martin' })).toHaveAttribute('href', '/players/12');

		await fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(button).toHaveFocus();
	});

	it('leaves out a code the front does not know and one the collection has no earned slot for', () => {
		const notEarned = { code: 'champion', tier: 0, discipline: null };
		renderHeader({ badges: [unknown, notEarned, pinned[2]] });

		expect(screen.getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual([
			'Clean sweep, badge earned 2 times'
		]);
	});

	it('renders nothing for a person without a badge', () => {
		const { container } = renderHeader({ badges: [], collection: badgeCollection([]) });

		expect(container.querySelector('*')).toBeNull();
	});

	it('speaks French', () => {
		renderHeader({}, 'fr');

		const list = screen.getByRole('list', { name: 'Vitrine' });
		expect(within(list).getByRole('button', { name: 'Razzia, badge obtenu 2 fois' })).toBeInTheDocument();
	});
});
