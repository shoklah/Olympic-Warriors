import { fireEvent, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import GameRow from './GameRow.svelte';
import { renderWith } from '$lib/test-utils';

const played = {
	team1Name: 'Bisons',
	team2Name: 'Aigles',
	score1: 12,
	score2: 9,
	isPlayed: true,
	refereeName: 'Cerfs'
};

describe('GameRow', () => {
	it('shows both teams, the score and the referee', () => {
		renderWith(GameRow, played);

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Bisons\s*12 : 9\s*Aigles/);
		expect(screen.getByTestId('game-row')).toHaveTextContent('ref: Cerfs');
	});

	it('dashes the score of an unplayed game', () => {
		renderWith(GameRow, {
			...played,
			team1Name: 'Cerfs',
			team2Name: 'Bisons',
			score1: null,
			score2: null,
			isPlayed: false,
			refereeName: 'Aigles'
		});

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Cerfs\s*— : —\s*Bisons/);
	});

	it('says played when a played game has no score', () => {
		renderWith(GameRow, { ...played, score1: null, score2: null });

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Bisons\s*played\s*Aigles/);
	});

	it('marks the winner and the loser', () => {
		const { container } = renderWith(GameRow, played);

		expect(container.querySelector('.winner')).toHaveTextContent('Bisons');
		expect(container.querySelector('.loser')).toHaveTextContent('Aigles');
	});

	it('marks neither team on a draw', () => {
		const { container } = renderWith(GameRow, { ...played, score1: 7, score2: 7 });

		expect(container.querySelector('.winner')).toBeNull();
		expect(container.querySelector('.loser')).toBeNull();
	});

	it('marks neither team without a score', () => {
		const { container } = renderWith(GameRow, { ...played, score1: null, score2: null });

		expect(container.querySelector('.winner')).toBeNull();
		expect(container.querySelector('.loser')).toBeNull();
	});

	it('links the team names when a href is given', () => {
		renderWith(GameRow, { ...played, team1Href: '/2026/teams/2', team2Href: '/2026/teams/1' });

		expect(screen.getByRole('link', { name: 'Bisons' })).toHaveAttribute(
			'href',
			'/2026/teams/2'
		);
		expect(screen.getByRole('link', { name: 'Aigles' })).toHaveAttribute('href', '/2026/teams/1');
	});

	// The accent sits too close to the body text: a link among text carries the stylesheet's
	// quiet-link (underlined on hover and focus), and the own team a dot drawn from its `own` class.
	it('marks the team links as links among text, and never the own team, which is no link', () => {
		renderWith(GameRow, {
			...played,
			team1Id: 2,
			team2Id: 1,
			highlightId: 1,
			team1Href: '/2026/teams/2',
			team2Href: '/2026/teams/1'
		});

		expect(screen.getByRole('link', { name: 'Bisons' })).toHaveClass('quiet-link');
		expect(screen.getByText('Aigles')).not.toHaveClass('quiet-link');
	});

	it('omits the referee line when there is no referee', () => {
		renderWith(GameRow, { ...played, refereeName: null });

		expect(screen.getByTestId('game-row')).not.toHaveTextContent('ref:');
	});

	it('renders plain names without a href', () => {
		renderWith(GameRow, played);

		expect(screen.queryByRole('link', { name: 'Bisons' })).toBeNull();
		expect(screen.getByText('Bisons')).toBeInTheDocument();
	});

	it('speaks French under fr', () => {
		renderWith(GameRow, { ...played, score1: null, score2: null }, 'fr');

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Bisons\s*joué\s*Aigles/);
		expect(screen.getByTestId('game-row')).toHaveTextContent('arbitre : Cerfs');
	});

	it('names an unknown team', () => {
		renderWith(GameRow, { ...played, team2Name: null }, 'en');

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Bisons\s*12 : 9\s*Unknown/);
	});

	it('puts the round label first when given', () => {
		renderWith(GameRow, { ...played, roundLabel: 'R1' });

		expect(screen.getByTestId('game-row')).toHaveTextContent(/^\s*R1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(screen.getByText('R1')).toHaveClass('round');
	});

	it('highlights the own team as plain text and keeps the other one a link', () => {
		renderWith(GameRow, {
			...played,
			team1Id: 2,
			team2Id: 1,
			highlightId: 1,
			team1Href: '/2026/teams/2',
			team2Href: '/2026/teams/1'
		});

		expect(screen.queryByRole('link', { name: 'Aigles' })).toBeNull();
		expect(screen.getByText('Aigles')).toHaveClass('own');
		expect(screen.getByText('Aigles')).toHaveClass('loser');
		expect(screen.getByRole('link', { name: 'Bisons' })).toHaveAttribute('href', '/2026/teams/2');
		expect(screen.getByRole('link', { name: 'Bisons' })).not.toHaveClass('own');
	});

	it('highlights nothing without a highlightId', () => {
		const { container } = renderWith(GameRow, { ...played, team1Id: 2, team2Id: 1 });
		expect(container.querySelector('.own')).toBeNull();
	});

	it('wraps the pairing in a button when onEdit is given and calls it on click', async () => {
		const onEdit = vi.fn();
		renderWith(GameRow, { ...played, onEdit });

		const button = screen.getByRole('button', { name: /Bisons\s*12 : 9\s*Aigles/ });
		await fireEvent.click(button);
		expect(onEdit).toHaveBeenCalledTimes(1);
		expect(screen.queryByRole('link')).toBeNull();
	});

	it('has no button without onEdit', () => {
		renderWith(GameRow, played);
		expect(screen.queryByRole('button')).toBeNull();
	});
});
