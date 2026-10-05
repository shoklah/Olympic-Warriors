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
});
