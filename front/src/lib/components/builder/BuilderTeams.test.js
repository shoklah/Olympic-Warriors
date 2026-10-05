import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import BuilderTeams from './BuilderTeams.svelte';

const players = builderPayload.players;
const base = {
	players,
	teams: [],
	unplaced: players.map((p) => p.id),
	result: null,
	skills: builderPayload.skills,
	perTeam: 3,
	locked: [],
	incomplete: new Set(),
	notesFor: () => []
};
const proposed = {
	...base,
	teams: [{ players: [1, 2, 3] }, { players: [4, 5] }],
	unplaced: [6],
	result: {
		unmet: [],
		teams: [
			{ rating: 6, skills: { CARD: 7, STR: 7 } },
			{ rating: 5, skills: { CARD: 5, STR: 6 } }
		]
	}
};

describe('BuilderTeams', () => {
	it('offers no move menu before teams are proposed', () => {
		renderWith(BuilderTeams, base);

		expect(screen.queryAllByRole('combobox')).toHaveLength(0);
	});

	it('offers the teams as targets once proposed', () => {
		renderWith(BuilderTeams, proposed);

		const tray = screen.getByRole('region', { name: 'To place' });
		const options = within(within(tray).getByRole('combobox')).getAllByRole('option').map((o) => o.textContent);
		expect(options).toEqual(['Move to…', 'Team 1', 'Team 2']);
	});

	it.each([
		['en', 'Strength 7.0'],
		['fr', 'Force 7.0']
	])('names the skill bars in the page language (%s)', (locale, title) => {
		const { container } = renderWith(BuilderTeams, proposed, locale);

		expect(container.querySelector('.bars li:nth-child(2)').getAttribute('title')).toBe(title);
	});

	it('puts a refused players-per-team value back and passes on a valid one', async () => {
		const { component } = renderWith(BuilderTeams, base);
		const heard = vi.fn();
		component.$on('perTeam', ({ detail }) => heard(detail));
		const input = screen.getByLabelText('Players per team');

		await fireEvent.change(input, { target: { value: '25' } });
		expect(input.value).toBe('3');
		await fireEvent.change(input, { target: { value: '3.5' } });
		expect(input.value).toBe('3');
		expect(heard).not.toHaveBeenCalled();

		await fireEvent.change(input, { target: { value: '4' } });
		expect(heard).toHaveBeenCalledWith(4);
	});
});
