import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { profile, profileUnranked } from '$lib/fixtures/players.js';

describe('player profile page', () => {
	it('shows the name, the all-time position and the average rank figure', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('heading', { level: 1, name: 'Xavier Baby' })).toBeInTheDocument();
		const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
		expect(within(breadcrumb).getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
		const position = screen.getByTestId('position');
		expect(position).toHaveTextContent(/3\s*all-time/);
		expect(position).toHaveAttribute('href', '/players');
		expect(
			screen.getByRole('link', { name: '3 all-time · position on the players leaderboard' })
		).toBe(position);
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Average rank\s*2\.5/);
		expect(screen.queryByTestId('beaten')).toBeNull();
		expect(screen.queryByText(/%/)).toBeNull();
		expect(screen.queryByText('Teams beaten')).toBeNull();
		expect(screen.queryByText('Équipes battues')).toBeNull();
		expect(screen.getByText('4 editions · 2 counted')).toBeInTheDocument();
		expect(screen.queryByText('No ranked edition yet')).toBeNull();
	});

	it('lists every edition newest first: running, ranked, without a team', () => {
		renderWith(Page, { data: { profile } });

		const rows = screen.getAllByTestId('edition-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/2030\s*Les Aigles\s*In progress/);
		expect(rows[1]).toHaveTextContent(/2026\s*MxM\s*2\s*\/ 6/);
		expect(rows[2]).toHaveTextContent(/2024\s*No team recorded\s*—/);
		expect(rows[3]).toHaveTextContent(/2023\s*Bisons\s*3\s*\/ 8/);
		expect(within(rows[1]).getByRole('link', { name: 'MxM' })).toHaveAttribute('href', '/2026/teams/21');
		expect(within(rows[1]).getByRole('link', { name: '2026' })).toHaveAttribute('href', '/2026');
		expect(within(rows[2]).queryAllByRole('link').map((a) => a.textContent.trim())).toEqual(['2024']);
	});

	it('lists the badges with their detail and rule, skipping unknown codes', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('heading', { level: 2, name: 'Badges' })).toBeInTheDocument();
		const tiles = screen.getAllByTestId('badge');
		expect(tiles).toHaveLength(4);
		expect(tiles[0]).toHaveTextContent(/Veteran\s*Tier 1 · 2026\s*Play 3, 5, then 10 editions/);
		expect(tiles[1]).toHaveTextContent(/Comrades in arms\s*with\s*Léa Martin\s*·\s*2026/);
		expect(within(tiles[1]).getByRole('link', { name: 'Léa Martin' })).toHaveAttribute('href', '/players/12');
		expect(tiles[2]).toHaveTextContent(/Specialist\s*Relay · Tier 1 · 2026/);
		expect(tiles[3]).toHaveTextContent(
			/Clean sweep\s*×2 · 2023 · 2026\s*Win three disciplines or more in one edition/
		);
		expect(screen.queryByText(/future-badge/)).toBeNull();
	});

	it('hides the detail separators from assistive tech, keeping the words apart', () => {
		renderWith(Page, { data: { profile } });

		// What a screen reader gets: the text outside aria-hidden nodes.
		const spoken = (el) => {
			const copy = el.cloneNode(true);
			copy.querySelectorAll('[aria-hidden="true"]').forEach((node) => node.remove());
			return copy.textContent.replace(/\s+/g, ' ').trim();
		};
		const details = screen.getAllByTestId('badge-detail');
		expect(details.map(spoken)).toEqual([
			'Tier 1 2026',
			'with Léa Martin 2026',
			'Relay Tier 1 2026',
			'×2 2023 2026'
		]);
		expect(details.map((detail) => detail.textContent.replace(/\s+/g, ' ').trim())).toEqual([
			'Tier 1 · 2026',
			'with Léa Martin · 2026',
			'Relay · Tier 1 · 2026',
			'×2 · 2023 · 2026'
		]);
	});

	it('leaves no dangling separator, nor an empty detail line, when a badge has no year', () => {
		const lea = { id: 12, first_name: 'Léa', last_name: 'Martin' };
		const badges = [
			{ code: 'comrades', tier: 0, years: [], discipline: null, partner: lea },
			{ code: 'champion', tier: 0, years: [], discipline: null, partner: null }
		];
		renderWith(Page, { data: { profile: { ...profileUnranked, badges } } });

		const tiles = screen.getAllByTestId('badge');
		expect(within(tiles[0]).getByTestId('badge-detail')).toHaveTextContent(/^with Léa Martin$/);
		expect(within(tiles[0]).getByRole('link', { name: 'Léa Martin' })).toHaveAttribute('href', '/players/12');
		expect(within(tiles[1]).queryByTestId('badge-detail')).toBeNull();
		expect(tiles[1]).toHaveTextContent(/^Champion\s*Win an edition$/);
	});

	it('has no badges section without badges', () => {
		renderWith(Page, { data: { profile: profileUnranked } });
		expect(screen.queryByRole('heading', { level: 2, name: 'Badges' })).toBeNull();
		expect(screen.queryAllByTestId('badge')).toHaveLength(0);
	});

	it('has no badges section for a payload without the badges key, like an older API', () => {
		const older = { ...profileUnranked };
		delete older.badges;
		renderWith(Page, { data: { profile: older } });
		expect(screen.getByRole('heading', { level: 1, name: 'Ana Petit' })).toBeInTheDocument();
		expect(screen.queryByRole('heading', { level: 2, name: 'Badges' })).toBeNull();
		expect(screen.queryAllByTestId('badge')).toHaveLength(0);
	});

	it('dashes the figures and says so when nothing is counted yet', () => {
		renderWith(Page, { data: { profile: profileUnranked } });

		expect(screen.queryByTestId('position')).toBeNull();
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Average rank\s*—/);
		expect(screen.queryByTestId('beaten')).toBeNull();
		expect(screen.getByText('No ranked edition yet')).toBeInTheDocument();
		expect(screen.getByText('1 edition · 0 counted')).toBeInTheDocument();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: { profile } }, 'fr');

		const breadcrumb = screen.getByRole('navigation', { name: "Fil d'Ariane" });
		expect(within(breadcrumb).getByRole('link', { name: 'Joueurs' })).toHaveAttribute('href', '/players');
		expect(screen.getByRole('heading', { level: 2, name: 'Éditions' })).toBeInTheDocument();
		expect(screen.getByTestId('position')).toHaveTextContent(/3\s*général/);
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Classement moyen\s*2,5/);
		expect(screen.queryByTestId('beaten')).toBeNull();
		expect(screen.getByText('4 éditions · 2 classées')).toBeInTheDocument();
		const rows = screen.getAllByTestId('edition-row');
		expect(rows[0]).toHaveTextContent(/2030\s*Les Aigles\s*En cours/);
		expect(rows[1]).toHaveTextContent(/2026\s*MxM\s*2\s*\/ 6/);
		expect(rows[2]).toHaveTextContent(/2024\s*Pas d'équipe/);
		const tiles = screen.getAllByTestId('badge');
		expect(tiles[0]).toHaveTextContent(/Vétéran\s*Niveau 1 · 2026/);
		expect(tiles[1]).toHaveTextContent(/Compagnons d'armes\s*avec\s*Léa Martin/);
		expect(tiles[2]).toHaveTextContent(/Spécialiste\s*Relais · Niveau 1 · 2026/);
		expect(tiles[3]).toHaveTextContent(
			/Razzia\s*×2 · 2023 · 2026\s*Gagner au moins trois épreuves lors d'une même édition/
		);
	});

	it('says nothing is ranked yet, in French too', () => {
		renderWith(Page, { data: { profile: profileUnranked } }, 'fr');

		expect(screen.getByText("Aucune édition classée pour l'instant")).toBeInTheDocument();
	});
});
