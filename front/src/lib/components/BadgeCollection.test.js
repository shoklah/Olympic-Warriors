import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { badgeCollection } from '$lib/badges';
import BadgeCollection from './BadgeCollection.svelte';

const badges = [
	{ code: 'champion', tier: 0, years: [2021, 2024], discipline: null, partner: null },
	{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null },
	{ code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null },
	{
		code: 'comrades',
		tier: 0,
		years: [2026],
		discipline: null,
		partner: { id: 12, first_name: 'Léa', last_name: 'Martin' }
	},
	{ code: 'future-badge', tier: 0, years: [2026], discipline: null, partner: null }
];

/** BadgeCollection now takes the already-computed collection, like the profile page passes it. */
const renderCollection = (list, locale = 'en') => renderWith(BadgeCollection, { collection: badgeCollection(list) }, locale);

describe('BadgeCollection', () => {
	it('has a visually hidden "Badges" heading above the progress line', () => {
		renderCollection(badges);
		expect(screen.getByRole('heading', { level: 2, name: 'Badges' })).toBeInTheDocument();
	});

	it('shows the overall progress and the per-family counts', () => {
		renderCollection(badges);
		expect(screen.getByText('4 badges out of 63')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Podiums 1 of 5' })).toHaveTextContent('1/5');
		expect(screen.getByRole('heading', { name: 'Loyalty 1 of 6' })).toHaveTextContent('1/6');
		expect(screen.getByRole('heading', { name: 'Teammates 1 of 2' })).toHaveTextContent('1/2');
	});

	it('pluralises the overall progress line: 0, 1 and 2+', () => {
		renderCollection([]);
		expect(screen.getByText('0 badges out of 63')).toBeInTheDocument();

		renderCollection([{ code: 'champion', tier: 0, years: [2026], discipline: null, partner: null }]);
		expect(screen.getByText('1 badge out of 63')).toBeInTheDocument();

		renderCollection(badges);
		expect(screen.getByText('4 badges out of 63')).toBeInTheDocument();
	});

	it('renders every catalogue code as a slot button', () => {
		renderCollection(badges);
		expect(screen.getAllByRole('button')).toHaveLength(63);
	});

	it('names an earned-once slot without a count, and a locked slot without one either', () => {
		renderCollection(badges);
		expect(screen.getByRole('button', { name: 'Veteran, badge earned' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Wooden spoon, badge locked' })).toBeInTheDocument();
	});

	it('names a repeated slot with a spoken count, not "×N", and still shows the ×N chip', () => {
		renderCollection(badges);
		const champion = screen.getByRole('button', { name: 'Champion, badge earned 2 times' });
		expect(champion).toHaveTextContent('×2');
	});

	it('opens a sheet on click, named after the badge, with the entry detail and next tier', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Veteran/ }));

		const dialog = screen.getByRole('dialog', { name: 'Veteran' });
		expect(within(dialog).getByText('Badge earned')).toBeInTheDocument();
		expect(dialog).toHaveTextContent('Play 3, 5, then 10 editions');
		expect(dialog).toHaveTextContent('Tier 1');
		expect(dialog).toHaveTextContent('2026');
		expect(dialog).toHaveTextContent('Next tier: 5 editions');
	});

	it('shows the partner link of a comrades entry first', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Comrades in arms/ }));

		const link = screen.getByRole('link', { name: 'Léa Martin' });
		expect(link).toHaveAttribute('href', '/players/12');
	});

	it('shows the first tier goal of a locked tiered slot', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Networker/ }));

		const dialog = screen.getByRole('dialog', { name: 'Networker' });
		expect(within(dialog).getByText('Badge locked')).toBeInTheDocument();
		expect(dialog).toHaveTextContent('First tier: 5 teammates');
	});

	it('shows the top-tier line for a badge at tier 3', async () => {
		renderCollection([{ code: 'veteran', tier: 3, years: [2020, 2022, 2027], discipline: null, partner: null }]);
		await fireEvent.click(screen.getByRole('button', { name: /^Veteran/ }));

		expect(screen.getByRole('dialog', { name: 'Veteran' })).toHaveTextContent('Top tier');
	});

	it('closes on Escape and gives focus back to the slot button', async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);
		expect(screen.getByRole('dialog')).toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('closes on a backdrop click and gives focus back to the slot button', async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);

		await fireEvent.click(screen.getByTestId('backdrop'));
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('closes on the close button and gives focus back to the slot button', async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);

		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('speaks French', async () => {
		renderCollection(badges, 'fr');
		expect(screen.getByRole('heading', { level: 2, name: 'Badges' })).toBeInTheDocument();
		expect(screen.getByText('4 badges sur 63')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Palmarès 1 sur 5' })).toHaveTextContent('1/5');
		expect(screen.getByRole('button', { name: 'Cuillère de bois, badge à débloquer' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Champion, badge obtenu 2 fois' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /^Vétéran/ }));
		expect(screen.getByRole('dialog', { name: 'Vétéran' })).toHaveTextContent('Prochain niveau : 5 éditions');
	});

	it('speaks French for the 0-badge singular', () => {
		renderCollection([], 'fr');
		expect(screen.getByText('0 badge sur 63')).toBeInTheDocument();
	});

	it('gives every slot the rule as its accessible description, for every device', () => {
		renderCollection(badges);
		expect(screen.getByRole('button', { name: /^Champion/ })).toHaveAccessibleDescription('Win an edition');
		expect(screen.getByRole('button', { name: /^Wooden spoon/ })).toHaveAccessibleDescription(
			'Finish last in an edition of 4 teams or more'
		);
	});

	it('speaks the description in French too', () => {
		renderCollection(badges, 'fr');
		expect(screen.getByRole('button', { name: /^Champion/ })).toHaveAccessibleDescription('Gagner une édition');
	});

	it('hides a shown tooltip on Escape even when it is only hovered, without moving focus, and shows it again once the pointer leaves', async () => {
		renderCollection(badges);
		document.body.focus(); // nothing focused: only hover can be showing the tooltip
		const champion = screen.getByRole('button', { name: /^Champion/ });

		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('tooltip-shown');

		// The keydown listener lives on window, not on the (unfocused) slot button: a
		// hover-only tooltip has no element with focus to dispatch on.
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(champion).not.toHaveClass('tooltip-shown');
		expect(champion).not.toHaveFocus();
		expect(document.body).toHaveFocus();

		await fireEvent.mouseLeave(champion);
		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('tooltip-shown');
	});

	it('keeps a tooltip dismissed while either hover or focus remains, only resetting once both are gone', async () => {
		renderCollection(badges);
		const champion = screen.getByRole('button', { name: /^Champion/ });

		champion.focus();
		await fireEvent.mouseEnter(champion);
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(champion).not.toHaveClass('tooltip-shown');

		// The pointer leaves, but focus is still on the slot: still dismissed, not reshown.
		await fireEvent.mouseLeave(champion);
		expect(champion).not.toHaveClass('tooltip-shown');

		// Focus leaves too: only now does the dismissal clear.
		await fireEvent.blur(champion);
		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('tooltip-shown');
	});

	it("shows only the hovered slot's tooltip, even while another slot keeps keyboard focus", async () => {
		renderCollection(badges);
		const champion = screen.getByRole('button', { name: /^Champion/ });
		const veteran = screen.getByRole('button', { name: /^Veteran/ });

		await fireEvent.focus(champion);
		expect(champion).toHaveClass('tooltip-shown');

		await fireEvent.mouseEnter(veteran);
		expect(veteran).toHaveClass('tooltip-shown');
		expect(champion).not.toHaveClass('tooltip-shown');
	});

	it("treats focus returned from the closed sheet as dismissed, so its tooltip doesn't pop back up", async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);
		await fireEvent.keyDown(window, { key: 'Escape' }); // closes the sheet, returns focus

		expect(trigger).toHaveFocus();
		expect(trigger).not.toHaveClass('tooltip-shown');
	});

	it("threads badge_stats through to the sheet's rarity line", async () => {
		const badgeStats = { players: 47, holders: { champion: 12 } };
		renderWith(BadgeCollection, { collection: badgeCollection(badges), badgeStats });
		await fireEvent.click(screen.getByRole('button', { name: /^Champion/ }));

		expect(screen.getByRole('dialog', { name: 'Champion' })).toHaveTextContent(
			'26% of players have it (12 of 47)'
		);
	});

	it('shows no rarity line without badge_stats', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Champion/ }));

		expect(screen.getByRole('dialog', { name: 'Champion' })).not.toHaveTextContent('of players');
	});

	it('aligns the tooltip to the near edge for a slot close to the viewport edge, centred otherwise, off document.documentElement.clientWidth (excludes a classic scrollbar, unlike window.innerWidth)', async () => {
		renderCollection(badges);
		// jsdom gives clientWidth 0 by default (no real layout): stand in for a 1024px
		// content width, as document.documentElement.clientWidth would report with a
		// classic scrollbar eating into a 1024px window.innerWidth.
		Object.defineProperty(document.documentElement, 'clientWidth', { value: 1024, configurable: true });

		const champion = screen.getByRole('button', { name: /^Champion/ });
		vi.spyOn(champion, 'getBoundingClientRect').mockReturnValue({ left: 5, width: 70, right: 75 });
		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('align-left');
		expect(champion).not.toHaveClass('align-right');

		const woodenSpoon = screen.getByRole('button', { name: /^Wooden spoon/ });
		vi.spyOn(woodenSpoon, 'getBoundingClientRect').mockReturnValue({ left: 954, width: 70, right: 1024 });
		await fireEvent.mouseEnter(woodenSpoon);
		expect(woodenSpoon).toHaveClass('align-right');
		expect(woodenSpoon).not.toHaveClass('align-left');

		const veteran = screen.getByRole('button', { name: /^Veteran/ });
		vi.spyOn(veteran, 'getBoundingClientRect').mockReturnValue({ left: 477, width: 70, right: 547 });
		await fireEvent.mouseEnter(veteran);
		expect(veteran).not.toHaveClass('align-left');
		expect(veteran).not.toHaveClass('align-right');
	});
});
