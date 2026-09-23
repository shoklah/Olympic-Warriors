import { fireEvent, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import ScoreSheet from './ScoreSheet.svelte';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

const game = {
	id: 201,
	team1Id: 3,
	team1Name: 'Cerfs',
	team2Id: 2,
	team2Name: 'Bisons',
	refereeName: 'Aigles',
	isPlayed: false,
	score1: 0,
	score2: 0
};

describe('ScoreSheet', () => {
	it('renders both teams, the round and the referee, and posts the game id', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });

		const dialog = screen.getByRole('dialog', { name: 'Round 1 · ref: Aigles' });
		expect(dialog).toHaveTextContent(/Cerfs/);
		expect(dialog).toHaveTextContent(/Bisons/);
		const form = dialog.querySelector('form');
		expect(form).toHaveAttribute('action', '?/score');
		expect(form.querySelector('input[name="game"]')).toHaveValue('201');
	});

	it('steps the scores and never below zero', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });

		const [minus1, plus1] = screen.getAllByRole('button', { name: /Cerfs/ });
		const score1 = screen.getByLabelText('Cerfs');
		await fireEvent.click(plus1);
		await fireEvent.click(plus1);
		expect(score1).toHaveValue(2);
		await fireEvent.click(minus1);
		await fireEvent.click(minus1);
		await fireEvent.click(minus1);
		expect(score1).toHaveValue(0);
	});

	it('starts the played switch on for an unplayed game', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		expect(screen.getByRole('checkbox', { name: 'Played' })).toBeChecked();
	});

	it('reflects the loaded score of a played game', () => {
		renderWith(ScoreSheet, { game: { ...game, isPlayed: true, score1: 12, score2: 9 }, roundNumber: 2, open: true });
		expect(screen.getByLabelText('Cerfs')).toHaveValue(12);
		expect(screen.getByLabelText('Bisons')).toHaveValue(9);
		expect(screen.getByRole('checkbox', { name: 'Played' })).toBeChecked();
	});

	it('closes on cancel, on Escape and on the backdrop', async () => {
		const { component } = renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		const closed = vi.fn();
		component.$on('close', closed);

		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByTestId('backdrop'));
		expect(closed).toHaveBeenCalledTimes(3);
	});

	it('focuses the first score field when it opens', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(screen.getByLabelText('Cerfs')).toHaveFocus();
	});

	it('renders nothing when closed and shows the error line when given', () => {
		const { container } = renderWith(ScoreSheet, { game, roundNumber: 1, open: false });
		expect(container.querySelector('[role="dialog"]')).toBeNull();

		renderWith(ScoreSheet, { game, roundNumber: 1, open: true, error: 'orga.error.conflict' });
		expect(screen.getByRole('alert')).toHaveTextContent('Not possible for this edition or round');
	});

	it('speaks French under fr', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true }, 'fr');
		expect(screen.getByRole('dialog', { name: 'Tour 1 · arbitre : Aigles' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeInTheDocument();
		expect(screen.getByRole('checkbox', { name: 'Joué' })).toBeInTheDocument();
	});
});
