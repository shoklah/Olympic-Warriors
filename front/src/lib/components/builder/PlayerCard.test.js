import { fireEvent, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import PlayerCard from './PlayerCard.svelte';

const player = { id: 1, first_name: 'Léa', last_name: 'Martin', rating: 8 };

describe('PlayerCard', () => {
	it('has no move menu when there is nowhere to move to', () => {
		renderWith(PlayerCard, { player, teamCount: 0 });

		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('lists the other teams and the tray for a placed player', () => {
		renderWith(PlayerCard, { player, teamCount: 3, index: 1 });

		expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Move to…', 'Team 1', 'Team 3', 'Take out of the team']);
	});

	it('keeps the move menu in the page for the keyboard and touch, whatever the screen', () => {
		renderWith(PlayerCard, { player: { id: 1, first_name: 'Léa', last_name: 'Martin', rating: 5 }, teamCount: 2, index: 0 });

		expect(screen.getByRole('combobox', { name: 'Move Léa Martin' })).toBeInTheDocument();
	});

	it('marks the card while it is dragged', async () => {
		renderWith(PlayerCard, { player: { id: 1, first_name: 'Léa', last_name: 'Martin', rating: 5 }, teamCount: 2, index: 0 });
		const card = screen.getByRole('listitem');

		await fireEvent.dragStart(card, { dataTransfer: { setData: () => {}, effectAllowed: '' } });
		expect(card).toHaveClass('dragging');

		await fireEvent.dragEnd(card);
		expect(card).not.toHaveClass('dragging');
	});

	it('only widens the action row for the move menu, never when a button is pressed', async () => {
		renderWith(PlayerCard, { player, teamCount: 2, index: 0 });
		const actions = screen.getByRole('combobox').parentElement;

		await fireEvent.focus(screen.getByRole('button', { name: 'View Léa Martin profile' }));
		expect(actions).not.toHaveClass('menu-focused');

		await fireEvent.focus(screen.getByRole('combobox'));
		expect(actions).toHaveClass('menu-focused');

		await fireEvent.blur(screen.getByRole('combobox'));
		expect(actions).not.toHaveClass('menu-focused');
	});

	it('has an info button, in the tray as in a team, that asks to preview the player', async () => {
		for (const index of [-1, 0]) {
			const { component, unmount } = renderWith(PlayerCard, { player, teamCount: 2, index });
			const seen = [];
			component.$on('preview', (e) => seen.push(e.detail));

			const button = screen.getByRole('button', { name: 'View Léa Martin profile' });
			await fireEvent.click(button);

			expect(seen).toEqual([{ id: 1, opener: button }]);
			unmount();
		}
	});
});
