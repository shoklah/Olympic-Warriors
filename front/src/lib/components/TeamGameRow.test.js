import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import TeamGameRow from './TeamGameRow.svelte';

const base = {
	round: 0,
	role: 'play',
	opponentName: 'Bisons',
	team1Name: 'Bisons',
	team2Name: 'Aigles',
	isPlayed: true,
	ownScore: 9,
	theirScore: 12,
	result: 'loss'
};

describe('TeamGameRow', () => {
	it('shows a lost game', () => {
		render(TeamGameRow, base);

		expect(screen.getByTestId('game-row')).toHaveTextContent(
			'Round 1 · vs Bisons · 9 : 12 · lost'
		);
	});

	it('shows a won game and marks the outcome', () => {
		const { container } = render(TeamGameRow, {
			...base,
			opponentName: 'Aigles',
			ownScore: 12,
			theirScore: 9,
			result: 'win'
		});

		expect(screen.getByTestId('game-row')).toHaveTextContent(
			'Round 1 · vs Aigles · 12 : 9 · won'
		);
		expect(container.querySelector('.won')).toHaveTextContent('won');
	});

	it('shows a draw', () => {
		render(TeamGameRow, {
			...base,
			round: 1,
			opponentName: 'Cerfs',
			ownScore: 7,
			theirScore: 7,
			result: 'draw'
		});

		expect(screen.getByTestId('game-row')).toHaveTextContent(
			'Round 2 · vs Cerfs · 7 : 7 · draw'
		);
	});

	it('shows a game still to play', () => {
		render(TeamGameRow, {
			...base,
			opponentName: 'Cerfs',
			isPlayed: false,
			ownScore: null,
			theirScore: null,
			result: null
		});

		expect(screen.getByTestId('game-row')).toHaveTextContent('Round 1 · vs Cerfs · to play');
	});

	it('shows a played game without a score', () => {
		render(TeamGameRow, { ...base, ownScore: null, theirScore: null, result: null });

		expect(screen.getByTestId('game-row')).toHaveTextContent('Round 1 · vs Bisons · played');
	});

	it('shows a refereed game', () => {
		render(TeamGameRow, {
			...base,
			role: 'referee',
			opponentName: null,
			team1Name: 'Cerfs',
			team2Name: 'Bisons',
			isPlayed: false,
			ownScore: null,
			theirScore: null,
			result: null
		});

		expect(screen.getByTestId('game-row')).toHaveTextContent(
			'Round 1 · referee · Cerfs vs Bisons'
		);
	});
});
