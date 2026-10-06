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

	it('tags each skill bar with its short identifier', () => {
		renderWith(BuilderTeams, proposed);

		const first = screen.getByRole('region', { name: 'Team 1' });
		expect([...first.querySelectorAll('.bars .tag')].map((t) => t.textContent)).toEqual(['CARD', 'STR']);
		const second = screen.getByRole('region', { name: 'Team 2' });
		expect([...second.querySelectorAll('.bars .tag')].map((t) => t.textContent)).toEqual(['CARD', 'STR']);
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

	it('highlights the team a card is dragged over, and clears it when it leaves or drops', async () => {
		renderWith(BuilderTeams, proposed);
		const team = screen.getByRole('region', { name: 'Team 1' });

		await fireEvent.dragOver(team);
		expect(team).toHaveClass('over');

		await fireEvent.dragLeave(team, { relatedTarget: document.body });
		expect(team).not.toHaveClass('over');

		await fireEvent.dragOver(team);
		await fireEvent.drop(team, { dataTransfer: { getData: () => '6' } });
		expect(team).not.toHaveClass('over');
	});

	it('moves a card dropped on a team', async () => {
		const { component } = renderWith(BuilderTeams, proposed);
		const moves = [];
		component.$on('move', (event) => moves.push(event.detail));

		await fireEvent.drop(screen.getByRole('region', { name: 'Team 2' }), { dataTransfer: { getData: () => '6' } });

		expect(moves).toEqual([{ id: 6, to: 1 }]);
	});

	describe('toolbar and unmet requests', () => {
		const unmetResult = {
			...proposed.result,
			unmet: [
				{ kind: 'with', player: 1, target: 4, mutual: false },
				{ kind: 'avoid', player: 2, target: 3, mutual: false }
			]
		};

		it('says in one line that every request is met, with nothing to expand', () => {
			renderWith(BuilderTeams, proposed);

			expect(screen.getByText('Every confirmed request is met.')).toBeInTheDocument();
			expect(screen.queryByRole('button', { name: /unmet request/ })).toBeNull();
		});

		it('counts the unmet requests and shows them on demand', async () => {
			renderWith(BuilderTeams, { ...proposed, result: unmetResult });

			const head = screen.getByRole('button', { name: /2 unmet requests/ });
			expect(head).toHaveAttribute('aria-expanded', 'false');
			expect(screen.getByText(/Léa Martin wanted to be with Inès Moreau/)).not.toBeVisible();

			await fireEvent.click(head);

			expect(head).toHaveAttribute('aria-expanded', 'true');
			expect(screen.getByText(/Léa Martin wanted to be with Inès Moreau/)).toBeVisible();
		});

		it('sends undo, redo and the reset, and disables undo and redo when there is nothing to do', async () => {
			const { component } = renderWith(BuilderTeams, { ...proposed, canUndo: true, canRedo: false });
			const events = [];
			for (const name of ['undo', 'redo', 'reset']) component.$on(name, () => events.push(name));

			await fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
			await fireEvent.click(screen.getByRole('button', { name: 'Reset everything' }));

			expect(screen.getByRole('button', { name: 'Redo' })).toBeDisabled();
			expect(events).toEqual(['undo', 'reset']);
		});

		it('keeps the locked-size explanation for the screen reader and as a tooltip', () => {
			renderWith(BuilderTeams, proposed);

			const field = screen.getByLabelText('Players per team');
			expect(field).toBeDisabled();
			expect(field).toHaveAccessibleDescription('Reset everything to change this number.');
		});
	});
});
