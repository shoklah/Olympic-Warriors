import { tick } from 'svelte';
import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import BuilderRequests from './BuilderRequests.svelte';

const players = builderPayload.players;
const withText = (id, over) => players.map((p) => (p.id === id ? { ...p, ...over } : p));

describe('BuilderRequests', () => {
	it('reports a toggle when a suggested name is confirmed', async () => {
		const { component } = renderWith(BuilderRequests, { players, links: [] });
		const events = [];
		component.$on('toggle', (e) => events.push(e.detail));

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm Paul Durand' }));

		expect(events).toEqual([{ player: 1, kind: 'with', target: 2 }]);
	});

	it('shows a confirmed link as pressed', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 1, kind: 'with', target: 2 }] });

		expect(screen.getByRole('button', { name: 'Confirm Paul Durand' })).toHaveAttribute('aria-pressed', 'true');
	});

	it('says when a name matches nobody', () => {
		renderWith(BuilderRequests, { players: withText(2, { team_with: 'peu importe' }).map((p) => ({ ...p, team_avoid: '' })), links: [] });

		expect(screen.getAllByText('No matching player').length).toBeGreaterThan(0);
	});

	it('offers both candidates of an ambiguous first name', () => {
		renderWith(BuilderRequests, { players: withText(6, { team_with: 'Paul' }), links: [] });

		expect(screen.getAllByRole('button', { name: 'Confirm Paul Durand' }).length).toBeGreaterThan(0);
		expect(screen.getAllByRole('button', { name: 'Confirm Paul Petit' }).length).toBeGreaterThan(0);
	});

	it('shows a link added through "Another player" as pressed', async () => {
		const { component } = renderWith(BuilderRequests, { players, links: [] });
		component.$on('toggle', (e) => component.$set({ links: [{ player: e.detail.player, kind: e.detail.kind, target: e.detail.target }] }));

		const select = screen.getAllByRole('combobox', { name: /Another player… \(Paul Durand\)/ })[0];
		await fireEvent.change(select, { target: { value: '5' } });

		const pressed = screen.getAllByRole('button', { name: 'Confirm Bob Roux' }).filter((b) => b.getAttribute('aria-pressed') === 'true');

		expect(pressed).toHaveLength(1);
	});

	it('says so when nobody wrote a request', () => {
		renderWith(BuilderRequests, { players: players.map((p) => ({ ...p, team_with: '', team_avoid: '' })), links: [] });

		expect(screen.getByText('No requests to review.')).toBeInTheDocument();
	});

	it('groups both kinds of request of a player in one card', () => {
		const both = [
			{ id: 1, first_name: 'Léa', last_name: 'Martin', team_with: 'Paul Durand', team_avoid: 'Bob Roux' },
			{ id: 2, first_name: 'Paul', last_name: 'Durand', team_with: '', team_avoid: '' },
			{ id: 5, first_name: 'Bob', last_name: 'Roux', team_with: '', team_avoid: '' }
		];
		renderWith(BuilderRequests, { players: both, links: [] });

		const cards = screen.getAllByRole('heading', { level: 3 });
		expect(cards.map((h) => h.textContent)).toEqual(['Léa Martin']);
		expect(screen.getByRole('region', { name: 'Léa Martin: wants to be with' })).toBeInTheDocument();
		expect(screen.getByRole('region', { name: 'Léa Martin: would rather avoid' })).toBeInTheDocument();
	});

	it('lists the links added by hand under their own label, apart from the written names', () => {
		const roster = [
			{ id: 1, first_name: 'Léa', last_name: 'Martin', team_with: 'Zoé', team_avoid: '' },
			{ id: 2, first_name: 'Paul', last_name: 'Durand', team_with: '', team_avoid: '' }
		];
		renderWith(BuilderRequests, { players: roster, links: [{ player: 1, kind: 'with', target: 2 }] });

		const section = screen.getByRole('region', { name: 'Léa Martin: wants to be with' });
		const added = within(section).getByText('Added by hand').closest('li');
		expect(within(added).getByRole('button', { name: 'Confirm Paul Durand' })).toHaveAttribute('aria-pressed', 'true');
		// the written name that matched nobody keeps its own block
		expect(within(section).getByText('No matching player').closest('li')).not.toBe(added);
	});

	it('says what each line is: clear matches, then confirmed ones', () => {
		const { component } = renderWith(BuilderRequests, { players, links: [] });

		expect(screen.getAllByText('Clear match')).toHaveLength(4);
		expect(screen.queryByText('Confirmed')).toBeNull();

		component.$set({ links: [{ player: 1, kind: 'with', target: 2 }] });
		return vi.waitFor(() => {
			expect(screen.getAllByText('Clear match')).toHaveLength(3);
			expect(screen.getAllByText('Confirmed')).toHaveLength(1);
		});
	});

	it('says why a name matched', () => {
		renderWith(BuilderRequests, { players, links: [] });

		expect(screen.getByText('Full name · only one player')).toBeInTheDocument(); // « Paul Durand »
		expect(screen.getAllByText('First name · only one player')).toHaveLength(3); // « Zoé », « Léa », « Bob »
	});

	it('marks lines that need a decision and a name without a player', () => {
		const roster = [
			{ id: 1, first_name: 'Léa', last_name: 'Martin', team_with: 'Paul', team_avoid: 'Inez' },
			{ id: 2, first_name: 'Paul', last_name: 'Durand', team_with: 'peu importe', team_avoid: '' },
			{ id: 3, first_name: 'Paul', last_name: 'Petit', team_with: '', team_avoid: '' },
			{ id: 4, first_name: 'Inès', last_name: 'Moreau', team_with: '', team_avoid: '' }
		];
		renderWith(BuilderRequests, { players: roster, links: [] });

		expect(screen.getByText('Choose')).toBeInTheDocument();
		expect(screen.getByText('2 players possible, pick one')).toBeInTheDocument();
		expect(screen.getByText('Check')).toBeInTheDocument();
		expect(screen.getByText('Close spelling, check it is the right person')).toBeInTheDocument();
		expect(screen.getByText('No match')).toBeInTheDocument();
		expect(screen.getByText('No matching player')).toBeInTheDocument();
	});

	it('counts the requests and tells the review apart from what is confirmed', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 1, kind: 'with', target: 2 }] });

		expect(screen.getByText('4 requests')).toBeInTheDocument();
		expect(screen.getByText('1 confirmed')).toBeInTheDocument();
		expect(screen.getByText('3 to review')).toBeInTheDocument();
	});

	it('mentions the requests with no match in the count only when there are some', () => {
		renderWith(BuilderRequests, { players: withText(2, { team_with: 'peu importe' }), links: [] });

		expect(screen.getByText(/with no match/)).toBeInTheDocument();
	});

	it('offers to confirm the clear matches in one click, and reports them all at once', async () => {
		const { component } = renderWith(BuilderRequests, { players, links: [] });
		const events = [];
		component.$on('confirmClear', (e) => events.push(e.detail));

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm 4 clear matches' }));

		expect(events).toEqual([[
			{ player: 1, kind: 'with', target: 2 },
			{ player: 1, kind: 'avoid', target: 6 },
			{ player: 2, kind: 'with', target: 1 },
			{ player: 4, kind: 'avoid', target: 5 }
		]]);
	});

	// Two players are called Paul, so « Paul » is ambiguous; the Pauls themselves write nothing, since a Paul is not offered himself.
	it('has no bulk button when no line is clear', () => {
		renderWith(BuilderRequests, { players: players.map((p) => ({ ...p, team_with: p.first_name === 'Paul' ? '' : 'Paul', team_avoid: '' })), links: [] });

		expect(screen.queryByRole('button', { name: /clear match/ })).toBeNull();
	});

	it('shows a confirmed chip as pressed with a status of its own', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 4, kind: 'avoid', target: 5 }] });

		const section = screen.getByRole('region', { name: 'Inès Moreau: would rather avoid' });
		expect(within(section).getByRole('button', { name: 'Confirm Bob Roux' })).toHaveAttribute('aria-pressed', 'true');
		expect(within(section).getByText('Confirmed')).toBeInTheDocument();
	});

	it('speaks French', () => {
		renderWith(BuilderRequests, { players, links: [{ player: 1, kind: 'with', target: 2 }] }, 'fr');

		for (const text of ['4 demandes', '1 confirmée', '3 à examiner']) expect(screen.getByText(text)).toBeInTheDocument();
		expect(screen.getByLabelText('À examiner seulement')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Confirmer 3 correspondances sûres' })).toBeInTheDocument();
		expect(screen.getAllByText('Correspondance sûre')).toHaveLength(3);
		expect(screen.getByText('Confirmé')).toBeInTheDocument();
		expect(screen.getAllByText('Prénom · un seul joueur', { exact: false }).length).toBeGreaterThan(0);
	});

	describe('toolbar', () => {
		it('sends undo and redo, and disables them when there is nothing to do', async () => {
			const { component } = renderWith(BuilderRequests, { players, links: [], canUndo: true, canRedo: false });
			const events = [];
			component.$on('undo', () => events.push('undo'));

			await fireEvent.click(screen.getByRole('button', { name: 'Undo' }));

			expect(events).toEqual(['undo']);
			expect(screen.getByRole('button', { name: 'Redo' })).toBeDisabled();
		});

		it('hides the confirmed lines on demand and says so when nothing is left to review', async () => {
			const links = [{ player: 1, kind: 'with', target: 2 }];
			renderWith(BuilderRequests, { players, links });
			expect(screen.getByRole('button', { name: 'Confirm Paul Durand' })).toBeInTheDocument();

			await fireEvent.click(screen.getByLabelText('To review only'));

			expect(screen.queryByRole('button', { name: 'Confirm Paul Durand' })).toBeNull();
			expect(screen.getByRole('button', { name: 'Confirm Zoé Blanc' })).toBeInTheDocument();
			expect(screen.queryByText('Everything is confirmed.')).toBeNull();
		});

		it('says everything is confirmed when the filter leaves no line', async () => {
			const all = [
				{ player: 1, kind: 'with', target: 2 },
				{ player: 1, kind: 'avoid', target: 6 },
				{ player: 2, kind: 'with', target: 1 },
				{ player: 4, kind: 'avoid', target: 5 }
			];
			renderWith(BuilderRequests, { players, links: all });

			await fireEvent.click(screen.getByLabelText('To review only'));

			expect(screen.getByText('Everything is confirmed.')).toBeInTheDocument();
		});

		it('keeps a line in view once it is confirmed, until the filter is switched off and on again', async () => {
			const { component } = renderWith(BuilderRequests, { players, links: [] });
			component.$on('toggle', ({ detail }) => component.$set({ links: [{ player: detail.player, kind: detail.kind, target: detail.target }] }));
			await fireEvent.click(screen.getByLabelText('To review only'));
			const chip = screen.getByRole('button', { name: 'Confirm Paul Durand' });
			chip.focus();

			await fireEvent.click(chip);

			expect(chip).toHaveAttribute('aria-pressed', 'true');
			expect(document.activeElement).toBe(chip);

			await fireEvent.click(screen.getByLabelText('To review only'));
			await fireEvent.click(screen.getByLabelText('To review only'));
			expect(screen.queryByRole('button', { name: 'Confirm Paul Durand' })).toBeNull();
		});

		it('moves focus to the toolbar when the bulk confirm button has done its job', async () => {
			const { component } = renderWith(BuilderRequests, { players, links: [], canUndo: true });
			component.$on('confirmClear', ({ detail }) => component.$set({ links: detail }));
			const button = screen.getByRole('button', { name: 'Confirm 4 clear matches' });
			button.focus();

			await fireEvent.click(button);
			await tick();

			expect(screen.queryByRole('button', { name: /clear match/ })).toBeNull();
			expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Undo' }));
		});
	});

	describe('ignoring a request', () => {
		it('offers an Ignore button per line that sends the line and its candidates', async () => {
			const { component } = renderWith(BuilderRequests, { players, links: [] });
			const events = [];
			component.$on('ignore', (e) => events.push(e.detail));

			await fireEvent.click(screen.getByRole('button', { name: 'Ignore « Paul Durand »' }));

			expect(events).toEqual([{ player: 1, kind: 'with', text: 'Paul Durand', on: true, drop: [2] }]);
		});

		it('greys an ignored line, takes its candidates off, offers to take it back and counts it apart', async () => {
			const ignored = [{ player: 1, kind: 'with', text: 'Paul Durand' }];
			const { component } = renderWith(BuilderRequests, { players, links: [], ignored });
			const events = [];
			component.$on('ignore', (e) => events.push(e.detail));

			expect(screen.queryByRole('button', { name: 'Confirm Paul Durand' })).toBeNull();
			expect(screen.getByText('Ignored')).toBeInTheDocument();
			expect(screen.getByText('Ignored: shown on no card')).toBeInTheDocument();
			expect(screen.getByText('1 ignored')).toBeInTheDocument();

			await fireEvent.click(screen.getByRole('button', { name: 'Stop ignoring « Paul Durand »' }));

			expect(events).toEqual([{ player: 1, kind: 'with', text: 'Paul Durand', on: false, drop: [2] }]);
		});

		it('leaves an ignored line out of the bulk confirm and out of « to review only »', async () => {
			const ignored = [{ player: 1, kind: 'with', text: 'Paul Durand' }];
			const { component } = renderWith(BuilderRequests, { players, links: [], ignored });
			const confirmed = [];
			component.$on('confirmClear', (e) => confirmed.push(...e.detail));

			await fireEvent.click(screen.getByRole('button', { name: 'Confirm 3 clear matches' }));
			expect(confirmed.some((l) => l.player === 1 && l.kind === 'with')).toBe(false);

			await fireEvent.click(screen.getByLabelText('To review only'));
			expect(screen.queryByRole('button', { name: 'Stop ignoring « Paul Durand »' })).toBeNull();
		});

		it('speaks French', () => {
			renderWith(BuilderRequests, { players, links: [], ignored: [{ player: 1, kind: 'with', text: 'Paul Durand' }] }, 'fr');

			expect(screen.getByRole('button', { name: 'Ne plus ignorer « Paul Durand »' })).toBeInTheDocument();
			expect(screen.getByText('Ignorée')).toBeInTheDocument();
			expect(screen.getByText('1 ignorée')).toBeInTheDocument();
		});
	});
});
