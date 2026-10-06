import { fireEvent, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import PlayerSheet from './PlayerSheet.svelte';

const { players, skills } = builderPayload;
const byId = (id) => players.find((p) => p.id === id);
const props = (id, over = {}) => ({ open: true, player: byId(id), skills, teamIndex: -1, ...over });
const dialog = () => screen.getByRole('dialog', { name: /./ });

describe('PlayerSheet', () => {
	it('renders nothing while closed', () => {
		renderWith(PlayerSheet, props(1, { open: false }));

		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('shows the name, the summary and one bar per skill', () => {
		renderWith(PlayerSheet, props(1, { player: { ...byId(1), global_level: 6 } }));

		const sheet = within(screen.getByRole('dialog', { name: 'Léa Martin' }));
		expect(sheet.getByText('To place')).toBeInTheDocument();
		expect(sheet.getByText('Computed rating').parentElement).toHaveTextContent(/Computed rating\s*8/);
		expect(sheet.getByText('Overall level (self-rated)').parentElement).toHaveTextContent(/self-rated\)\s*6/);
		expect(sheet.getByText('At least four hours a week')).toBeInTheDocument();
		expect(sheet.getByText('Cardio').parentElement).toHaveTextContent('9');
		expect(sheet.getByText('Strength').parentElement).toHaveTextContent('7');
		expect(sheet.queryByText('estimated')).toBeNull();
		expect(sheet.queryByText('Incomplete profile')).toBeNull();
	});

	it('says which team the player is in', () => {
		renderWith(PlayerSheet, props(1, { teamIndex: 2 }));

		expect(within(dialog()).getByText('Team 3')).toBeInTheDocument();
	});

	it('marks estimated skills and the incomplete profile, and hides the global level and dashes the frequency when unknown', () => {
		renderWith(PlayerSheet, props(5, { player: { ...byId(5), global_level: null } }));

		const sheet = within(dialog());
		expect(sheet.getAllByText('estimated')).toHaveLength(2);
		expect(sheet.getByText('Incomplete profile')).toBeInTheDocument();
		expect(sheet.queryByText('Overall level (self-rated)')).toBeNull();
		expect(sheet.getByText('Sport frequency').parentElement).toHaveTextContent(/Sport frequency\s*—/);
	});

	it('lists the sports with their level, or says there is none', () => {
		const { unmount } = renderWith(PlayerSheet, props(3));
		expect(within(dialog()).getByText('Judo · In a club, with competitions')).toBeInTheDocument();
		unmount();

		renderWith(PlayerSheet, props(1));
		expect(within(dialog()).getByText('No sport given')).toBeInTheDocument();
	});

	it('shows the practice and the notes, and leaves out a level nobody gave', () => {
		const sports = [
			{ sport: 'Tennis', level: 'league', practice: 'no_longer', notes: 'Classé 30/5' },
			{ sport: 'Historique (import)', level: '', practice: '', notes: 'Foot - 6 ans\nJudo - 2 ans' }
		];
		renderWith(PlayerSheet, props(3, { player: { ...byId(3), sports } }));

		const sheet = within(dialog());
		expect(sheet.getByText('Tennis · In a club, with competitions · No longer playing')).toBeInTheDocument();
		expect(sheet.getByText('Classé 30/5')).toBeInTheDocument();
		expect(sheet.getByText('Historique (import)')).toBeInTheDocument();
		expect(sheet.getByText(/Foot - 6 ans/)).toBeInTheDocument();
		expect(sheet.queryByText(/register\./)).toBeNull();
	});

	it('closes on Escape and on its button', async () => {
		const { component } = renderWith(PlayerSheet, props(1));
		let closed = 0;
		component.$on('close', () => closed++);

		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));

		expect(closed).toBe(2);
	});

	it('gives focus back to the opener on close', async () => {
		const opener = document.createElement('button');
		document.body.append(opener);
		renderWith(PlayerSheet, props(1, { opener }));
		await tick();

		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));

		expect(document.activeElement).toBe(opener);
		opener.remove();
	});

	it('speaks French', () => {
		renderWith(PlayerSheet, props(3, { teamIndex: 0 }), 'fr');

		const sheet = within(screen.getByRole('dialog', { name: 'Paul Petit' }));
		expect(sheet.getByText('Équipe 1')).toBeInTheDocument();
		expect(sheet.getByText('Force')).toBeInTheDocument();
		expect(sheet.getByRole('button', { name: 'Fermer' })).toBeInTheDocument();
	});

	describe('compare', () => {
		const candidates = players.filter((p) => p.id !== 1).map((p) => ({ id: p.id, name: `${p.first_name} ${p.last_name}`, teamIndex: p.id === 2 ? 1 : -1, rating: p.rating }));
		const compareProps = (over = {}) => props(1, { teamIndex: 0, candidates, ...over });

		it('opens a picker listing everyone else with their team, and filters without accents', async () => {
			renderWith(PlayerSheet, compareProps());

			await fireEvent.click(screen.getByRole('button', { name: 'Compare with…' }));
			const sheet = within(dialog());
			expect(sheet.getAllByRole('button', { name: /\d$/ })).toHaveLength(5);
			expect(sheet.getByRole('button', { name: /Paul Durand.*Team 2/ })).toBeInTheDocument();

			await fireEvent.input(sheet.getByRole('searchbox'), { target: { value: 'ines' } });
			expect(sheet.getAllByRole('button', { name: /\d$/ })).toHaveLength(1);
			expect(sheet.getByRole('button', { name: /Inès Moreau/ })).toBeInTheDocument();

			await fireEvent.input(sheet.getByRole('searchbox'), { target: { value: 'zzz' } });
			expect(sheet.getByText('No player found')).toBeInTheDocument();
		});

		it('dispatches the chosen player, and Escape closes the picker before the sheet', async () => {
			const { component } = renderWith(PlayerSheet, compareProps());
			const events = [];
			component.$on('compare', (e) => events.push(['compare', e.detail.id]));
			component.$on('close', () => events.push(['close']));

			await fireEvent.click(screen.getByRole('button', { name: 'Compare with…' }));
			await fireEvent.keyDown(window, { key: 'Escape' });
			expect(screen.queryByRole('searchbox')).toBeNull();
			expect(events).toEqual([]);

			await fireEvent.click(screen.getByRole('button', { name: 'Compare with…' }));
			await fireEvent.click(screen.getByRole('button', { name: /Paul Durand/ }));
			expect(events).toEqual([['compare', 2]]);

			await fireEvent.keyDown(window, { key: 'Escape' });
			expect(events.at(-1)).toEqual(['close']);
		});

		it('draws the butterfly table: both values per skill, the leader, the estimated side', () => {
			renderWith(PlayerSheet, compareProps({ other: byId(5), otherTeamIndex: 1, swapReason: null }));

			const table = within(screen.getByRole('table'));
			expect(table.getByRole('columnheader', { name: /Léa Martin/ })).toBeInTheDocument();
			expect(table.getByRole('columnheader', { name: /Bob Roux/ })).toBeInTheDocument();
			const row = table.getByRole('row', { name: /Cardio/ });
			expect(row).toHaveTextContent(/9.*Cardio.*3/);
			expect(within(row).getByText('+6')).toBeInTheDocument();
			expect(table.getAllByText('estimated')).toHaveLength(2);
			expect(table.getByText('Incomplete profile')).toBeInTheDocument();
		});

		it('swaps with the ids, or says why it cannot', async () => {
			const { component, unmount } = renderWith(PlayerSheet, compareProps({ other: byId(2), otherTeamIndex: 1 }));
			const swaps = [];
			component.$on('swap', (e) => swaps.push(e.detail));

			await fireEvent.click(screen.getByRole('button', { name: 'Swap' }));
			expect(swaps).toEqual([{ a: 1, b: 2 }]);
			unmount();

			for (const [reason, text] of [
				['locked', 'A locked player cannot be swapped.'],
				['sameTeam', 'Both players are in the same team.'],
				['bothTray', 'Both players are still to place.']
			]) {
				const r = renderWith(PlayerSheet, compareProps({ other: byId(2), swapReason: reason }));
				const button = screen.getByRole('button', { name: 'Swap' });
				expect(button).toBeDisabled();
				expect(button).toHaveAccessibleDescription(text);
				r.unmount();
			}
		});

		it('previews the swap with a word beside each change', () => {
			const swapView = { teams: [{ index: 0, before: 6.44, after: 6.7 }, { index: 1, before: 5, after: 4.2 }], unmet: { before: 5, after: 3 } };
			renderWith(PlayerSheet, compareProps({ other: byId(2), otherTeamIndex: 1, swapView }));

			expect(screen.getByText('Team 1: 6.4 → 6.7 (up)')).toBeInTheDocument();
			expect(screen.getByText('Team 2: 5.0 → 4.2 (down)')).toBeInTheDocument();
			expect(screen.getByText('Unmet requests: 5 → 3 (better)')).toBeInTheDocument();
		});

		it('goes back to the picker and closes the comparison', async () => {
			const { component } = renderWith(PlayerSheet, compareProps({ other: byId(2) }));
			let closed = 0;
			component.$on('uncompare', () => closed++);

			await fireEvent.click(screen.getByRole('button', { name: 'Close comparison' }));
			expect(closed).toBe(1);

			await fireEvent.click(screen.getByRole('button', { name: 'Change' }));
			expect(screen.getByRole('searchbox')).toBeInTheDocument();
		});

		it('speaks French', async () => {
			renderWith(PlayerSheet, compareProps({ other: byId(2), swapReason: 'locked' }), 'fr');

			expect(screen.getByRole('button', { name: 'Échanger' })).toBeDisabled();
			expect(screen.getByText('Un joueur verrouillé ne peut pas être échangé.')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Fermer la comparaison' })).toBeInTheDocument();
		});
	});
});
