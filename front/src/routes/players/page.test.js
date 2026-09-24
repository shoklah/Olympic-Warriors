import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { leaderboard } from '$lib/fixtures/players.js';

const data = { players: leaderboard };
const ranked = leaderboard.filter((p) => p.position !== null);
const waiting = leaderboard.filter((p) => p.position === null);

describe('players leaderboard page', () => {
	it('ranks players by their places, best first, with a spoken sentence', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { level: 1, name: 'Players' })).toBeInTheDocument();
		expect(screen.getByText('The Warriors hall of fame')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(
			/1\s*Léa Martin\s*1\s*2\s*1st place in 2024, 2nd place in 2026, average rank 1\.5, showcase: Champion, Veteran, Networker\s*1\.5\s*avg rank/
		);
		// Without a photo the avatar shows the initials: text, but aria-hidden, so the link's
		// name below leaves them out.
		expect(rows[1]).toHaveTextContent(
			/2\s*HM\s*Hugo Maurinier\s*1\s*1st place in 2025, average rank 1\.0\s*1\.0\s*avg rank/
		);
		expect(rows[2]).toHaveTextContent(
			/2\s*IM\s*Inès Moreau\s*1\s*1st place in 2025, average rank 1\.0, showcase: Specialist\s*1\.0\s*avg rank/
		);
		expect(rows[3]).toHaveTextContent(
			/4\s*Xavier Baby\s*2\s*3\s*4\s*2nd place in 2026, 3rd place in 2023, 4th place in 2021, average rank 3\.0, showcase: Clean sweep, Specialist, Comrades in arms\s*3\.0\s*avg rank/
		);
		expect(rows[0]).toHaveAttribute('href', '/players/12');
		expect(within(rows[0]).getByTestId('places')).toHaveAttribute('aria-hidden', 'true');
		expect(within(rows[0]).getByTestId('average')).toHaveAttribute('aria-hidden', 'true');
		expect(within(rows[0]).getByText('avg')).toHaveClass('short');
		rows.forEach((row) => expect(within(row).getByTestId('average')).toBeInTheDocument());
		expect(
			screen.getByRole('link', {
				name: /^1\s*Léa Martin\s*1st place in 2024, 2nd place in 2026, average rank 1\.5, showcase: Champion, Veteran, Networker$/
			})
		).toBeInTheDocument();
		expect(
			screen.getByRole('link', { name: /^2\s*Hugo Maurinier\s*1st place in 2025, average rank 1\.0$/ })
		).toBeInTheDocument();
	});

	it("draws each player's avatar before the name: the small photo, lazily, or the initials", () => {
		renderWith(Page, { data });

		const [lea, hugo] = screen.getAllByTestId('player-row');
		const photo = lea.querySelector('img[src^="/media/"]');
		expect(photo).toHaveAttribute('src', '/media/avatars/12-4f1c2a9b7e3d-sm.webp');
		expect(photo).toHaveAttribute('alt', '');
		expect(photo).toHaveAttribute('loading', 'lazy');
		expect(photo.closest('[aria-hidden="true"]')).not.toBeNull();
		expect(hugo.querySelector('img[src^="/media/"]')).toBeNull();
		expect(within(hugo).getByText('HM')).toHaveAttribute('aria-hidden', 'true');
		// Before the name, in document order.
		const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
		expect(follows(photo, within(lea).getByText('Léa Martin'))).toBe(true);
		expect(follows(within(hugo).getByText('HM'), within(hugo).getByText('Hugo Maurinier'))).toBe(true);
	});

	it('shows the showcase as hidden medallions, and no showcase line for a player without a badge', () => {
		renderWith(Page, { data });

		const [lea, hugo, ines] = screen.getAllByTestId('player-row');
		const showcase = within(lea).getByTestId('showcase');
		expect(showcase).toHaveAttribute('aria-hidden', 'true');
		expect(showcase.querySelectorAll('[data-metal]')).toHaveLength(3);
		expect(within(ines).getByTestId('showcase').querySelectorAll('[data-metal]')).toHaveLength(1);
		expect(within(hugo).queryByTestId('showcase')).toBeNull();
		expect(hugo).not.toHaveTextContent('showcase');
	});

	it('colours each place like a medal', () => {
		renderWith(Page, { data });

		const places = within(screen.getAllByTestId('player-row')[3]).getByTestId('places');
		const [second, third, fourth] = places.querySelectorAll('.place');
		expect(second).toHaveClass('silver');
		expect(third).toHaveClass('bronze');
		expect(fourth).not.toHaveClass('gold');
		expect(fourth).not.toHaveClass('silver');
		expect(fourth).not.toHaveClass('bronze');
	});

	it('medals tied players alike, not by row position', () => {
		renderWith(Page, { data });

		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('silver');
		expect(rows[2]).toHaveClass('silver');
		expect(rows[3]).not.toHaveClass('bronze');
	});

	it('shows the best places only past the cap, with the rest counted', () => {
		const ranks = [1, 1, 1, 1, 2, 2, 2, 3, 3, 3];
		const places = ranks.map((rank, i) => ({ year: 2030 - i, rank }));
		const busy = { ...ranked[0], places };
		renderWith(Page, { data: { players: [busy] } });

		const row = screen.getByTestId('player-row');
		const placesEl = within(row).getByTestId('places');
		expect(placesEl.querySelectorAll('.place')).toHaveLength(8);
		expect(placesEl.textContent.replace(/\s+/g, ' ').trim()).toBe('1 1 1 1 2 2 2 3 +2');
		// The spoken sentence still lists all ten.
		expect(row.textContent.match(/place in/g)).toHaveLength(10);
	});

	it('lists the players not ranked yet by name, with their editions and no position', () => {
		renderWith(Page, { data });

		expect(screen.getByRole('heading', { name: 'Not ranked yet' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('unranked-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/^\s*AP\s*Ana Petit\s*1 edition\s*$/);
		expect(rows[1]).toHaveTextContent(/^\s*Jules Roux\s*2 editions, showcase: Rookie\s*$/);
		expect(rows[1]).toHaveAttribute('href', '/players/41');
		expect(screen.getByRole('link', { name: /^Ana Petit\s*1 edition$/ })).toBe(rows[0]);
		// jsdom's name computation pads every child element with spaces, hence `\s*,`: the
		// comma opens the hidden showcase sentence, right after the visible edition count.
		expect(screen.getByRole('link', { name: /^Jules Roux\s*2 editions\s*, showcase: Rookie$/ })).toBe(rows[1]);
		expect(rows[1].querySelector('img[src^="/media/"]')).toHaveAttribute('src', '/media/avatars/41-0a1b2c3d4e5f-sm.webp');
		expect(within(rows[1]).getByTestId('showcase')).toHaveAttribute('aria-hidden', 'true');
		expect(within(rows[0]).queryByTestId('showcase')).toBeNull();
		rows.forEach((row) => expect(within(row).queryByTestId('average')).toBeNull());
	});

	it('has no not-ranked section when everyone is ranked', () => {
		renderWith(Page, { data: { players: ranked } });

		expect(screen.queryByRole('heading', { name: 'Not ranked yet' })).toBeNull();
	});

	it('has no ranked list when nobody is ranked yet', () => {
		const { container } = renderWith(Page, { data: { players: waiting } });

		expect(container.querySelector('ol')).toBeNull();
		expect(screen.queryAllByTestId('player-row')).toHaveLength(0);
		expect(screen.getAllByTestId('unranked-row')).toHaveLength(2);
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Joueurs' })).toBeInTheDocument();
		expect(screen.getByText('Le panthéon des Warriors')).toBeInTheDocument();
		const rows = screen.getAllByTestId('player-row');
		expect(rows[0]).toHaveTextContent(
			/1\s*Léa Martin\s*1\s*2\s*1re place en 2024, 2e place en 2026, classement moyen 1,5, vitrine : Champion, Vétéran, Rassembleur\s*1,5\s*classement moyen/
		);
		expect(
			screen.getByRole('link', {
				name: /^1\s*Léa Martin\s*1re place en 2024, 2e place en 2026, classement moyen 1,5, vitrine : Champion, Vétéran, Rassembleur$/
			})
		).toBeInTheDocument();
		expect(
			screen.getByRole('link', { name: /^Jules Roux\s*2 éditions\s*, vitrine : Bizut$/ })
		).toBeInTheDocument();
		expect(within(rows[0]).getByText('moy.')).toHaveClass('short');
		expect(screen.getByRole('heading', { name: 'Pas encore classés' })).toBeInTheDocument();
	});
});
