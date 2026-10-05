import { fireEvent, screen } from '@testing-library/svelte';
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
});
