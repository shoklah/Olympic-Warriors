import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { disciplineResults, disciplineSchedule, findDiscipline } from '$lib/edition';
import { summary, summaryAllRevealed } from '$lib/fixtures/summary.js';

const dataFor = (s, id) => ({
	summary: s,
	discipline: findDiscipline(s, id),
	results: disciplineResults(s, id),
	schedule: disciplineSchedule(s, id)
});

describe('discipline page', () => {
	it('shows points rows with the difference for a revealed points discipline', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Relay' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('result-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\s*Bisons\s*\+4\s*10 pts/);
		expect(rows[1]).toHaveTextContent(/2\s*Aigles\s*-2\s*5 pts/);
		expect(rows[2]).toHaveTextContent(/3\s*Cerfs\s*-2\s*0 pts/);
		// the whole row is the link, so its name carries the rank and the score too
		expect(rows[0]).toHaveAttribute('href', '/2026/teams/2');
		expect(rows[0]).toHaveClass('gold');
		expect(rows[1]).toHaveClass('silver');
		expect(rows[2]).toHaveClass('bronze');
	});

	it('marks the current discipline in the rail', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Orienteering' })).toHaveAttribute(
			'aria-disabled',
			'true'
		);
	});

	it('shows times for a revealed timed discipline', () => {
		render(Page, { data: dataFor(summaryAllRevealed, 11) });

		const rows = screen.getAllByTestId('result-row');
		expect(rows[0]).toHaveTextContent('1 Aigles');
		expect(rows[0]).toHaveTextContent('00:12:30');
	});

	it('shows the not-revealed message instead of rows', () => {
		render(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.queryAllByTestId('result-row')).toHaveLength(0);
	});

	it('shows the schedule by round with scores, dashes and referees', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Schedule' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Round 1' })).toBeInTheDocument();
		const games = screen.getAllByTestId('game-row');
		expect(games).toHaveLength(3);
		expect(games[0]).toHaveTextContent(/Bisons\s*12 : 9\s*Aigles/);
		expect(games[0]).toHaveTextContent('ref: Cerfs');
		expect(games[1]).toHaveTextContent(/Cerfs\s*— : —\s*Bisons/);
		expect(games[2]).toHaveTextContent(/Aigles\s*7 : 7\s*Cerfs/);
		expect(within(games[0]).getByRole('link', { name: 'Bisons' })).toHaveAttribute(
			'href',
			'/2026/teams/2'
		);
	});

	it('counts what is left to play beside each round heading', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Round 1' }).parentElement).toHaveTextContent(
			'1 to play'
		);
		expect(screen.getByRole('heading', { name: 'Round 2' }).parentElement).toHaveTextContent(
			'1 game'
		);
	});

	it('shows pairings without scores for an unrevealed discipline', () => {
		render(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.getAllByTestId('game-row')[0]).toHaveTextContent(/Aigles\s*played\s*Bisons/);
	});

	it('has no schedule section when every round is empty', () => {
		const empty = { ...summary, games: summary.games.filter((g) => g.discipline !== 10) };
		render(Page, { data: dataFor(empty, 10) });
		expect(screen.queryByRole('heading', { name: 'Schedule' })).toBeNull();
	});

	it('has no schedule section for a discipline without rounds', () => {
		render(Page, { data: dataFor({ ...summary, rounds: [], games: [] }, 10) });
		expect(screen.queryByRole('heading', { name: 'Schedule' })).toBeNull();
	});

	it('skips rounds with no games', () => {
		render(
			Page,
			{
				data: dataFor(
					{
						...summary,
						rounds: [...summary.rounds, { id: 23, discipline: 10, order: 2, is_over: false }]
					},
					10
				)
			}
		);
		expect(screen.queryByRole('heading', { name: 'Round 3' })).toBeNull();
	});
});
