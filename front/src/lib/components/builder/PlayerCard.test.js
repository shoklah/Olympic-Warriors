import { screen } from '@testing-library/svelte';
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
});
