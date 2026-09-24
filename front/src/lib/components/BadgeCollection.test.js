import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
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

describe('BadgeCollection', () => {
	it('shows the overall progress and the per-family counts', () => {
		renderWith(BadgeCollection, { badges });
		expect(screen.getByText('4 badges out of 63')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: /Podiums\s*1\/5/ })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: /Loyalty\s*1\/6/ })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: /Teammates\s*1\/2/ })).toBeInTheDocument();
	});

	it('renders every catalogue code as a slot button', () => {
		renderWith(BadgeCollection, { badges });
		expect(screen.getAllByRole('button')).toHaveLength(63);
	});

	it('names an earned slot with its count and a locked slot without one', () => {
		renderWith(BadgeCollection, { badges });
		const champion = screen.getByRole('button', { name: 'Champion, badge earned, ×2' });
		expect(champion).toHaveTextContent('×2');
		expect(screen.getByRole('button', { name: 'Wooden spoon, badge locked' })).toBeInTheDocument();
	});

	it('opens a sheet on click, named after the badge, with the entry detail and next tier', async () => {
		renderWith(BadgeCollection, { badges });
		await fireEvent.click(screen.getByRole('button', { name: /^Veteran/ }));

		const dialog = screen.getByRole('dialog', { name: 'Veteran' });
		expect(within(dialog).getByText('Badge earned')).toBeInTheDocument();
		expect(dialog).toHaveTextContent('Play 3, 5, then 10 editions');
		expect(dialog).toHaveTextContent('Tier 1');
		expect(dialog).toHaveTextContent('2026');
		expect(dialog).toHaveTextContent('Next tier: 5 editions');
	});

	it('shows the partner link of a comrades entry first', async () => {
		renderWith(BadgeCollection, { badges });
		await fireEvent.click(screen.getByRole('button', { name: /^Comrades in arms/ }));

		const link = screen.getByRole('link', { name: 'Léa Martin' });
		expect(link).toHaveAttribute('href', '/players/12');
	});

	it('shows the first tier goal of a locked tiered slot', async () => {
		renderWith(BadgeCollection, { badges });
		await fireEvent.click(screen.getByRole('button', { name: /^Networker/ }));

		const dialog = screen.getByRole('dialog', { name: 'Networker' });
		expect(within(dialog).getByText('Badge locked')).toBeInTheDocument();
		expect(dialog).toHaveTextContent('First tier: 20 teammates');
	});

	it('shows the top-tier line for a badge at tier 3', async () => {
		renderWith(BadgeCollection, {
			badges: [{ code: 'veteran', tier: 3, years: [2020, 2022, 2027], discipline: null, partner: null }]
		});
		await fireEvent.click(screen.getByRole('button', { name: /^Veteran/ }));

		expect(screen.getByRole('dialog', { name: 'Veteran' })).toHaveTextContent('Top tier');
	});

	it('closes on Escape and gives focus back to the slot button', async () => {
		renderWith(BadgeCollection, { badges });
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);
		expect(screen.getByRole('dialog')).toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('speaks French', async () => {
		renderWith(BadgeCollection, { badges }, 'fr');
		expect(screen.getByText('4 badges sur 63')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: /Palmarès\s*1\/5/ })).toBeInTheDocument();
		expect(
			screen.getByRole('button', { name: 'Cuillère de bois, badge à débloquer' })
		).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /^Vétéran/ }));
		expect(screen.getByRole('dialog', { name: 'Vétéran' })).toHaveTextContent('Prochain niveau : 5 éditions');
	});
});
