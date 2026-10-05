import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
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
});
