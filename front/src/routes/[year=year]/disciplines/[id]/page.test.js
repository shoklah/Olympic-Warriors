import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { disciplineEntries, disciplineResults, disciplineSchedule, findDiscipline } from '$lib/edition';
import { summary, summaryAllRevealed, summaryStaff } from '$lib/fixtures/summary.js';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

const dataFor = (s, id, editable = false) => ({
	summary: s,
	discipline: findDiscipline(s, id),
	results: disciplineResults(s, id),
	schedule: disciplineSchedule(s, id),
	entries: disciplineEntries(s, id),
	editable
});

describe('discipline page', () => {
	it('shows points rows with the difference for a revealed points discipline', () => {
		renderWith(Page, { data: dataFor(summary, 10) });

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
		renderWith(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Orienteering' })).not.toHaveAttribute(
			'aria-current'
		);
	});

	it('shows times for a revealed timed discipline', () => {
		renderWith(Page, { data: dataFor(summaryAllRevealed, 11) });

		const rows = screen.getAllByTestId('result-row');
		expect(rows[0]).toHaveTextContent('1 Aigles');
		expect(rows[0]).toHaveTextContent('12:30');
	});

	it('shows the not-revealed message instead of rows', () => {
		renderWith(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.queryAllByTestId('result-row')).toHaveLength(0);
	});

	it('shows the schedule by round with scores, dashes and referees', () => {
		renderWith(Page, { data: dataFor(summary, 10) });

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
		renderWith(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Round 1' }).parentElement).toHaveTextContent(
			'1 to play'
		);
		expect(screen.getByRole('heading', { name: 'Round 2' }).parentElement).toHaveTextContent(
			'1 game'
		);
	});

	it('shows pairings without scores for an unrevealed discipline', () => {
		renderWith(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.getAllByTestId('game-row')[0]).toHaveTextContent(/Aigles\s*played\s*Bisons/);
	});

	it('has no schedule section when every round is empty', () => {
		const empty = { ...summary, games: summary.games.filter((g) => g.discipline !== 10) };
		renderWith(Page, { data: dataFor(empty, 10) });
		expect(screen.queryByRole('heading', { name: 'Schedule' })).toBeNull();
	});

	it('has no schedule section for a discipline without rounds', () => {
		renderWith(Page, { data: dataFor({ ...summary, rounds: [], games: [] }, 10) });
		expect(screen.queryByRole('heading', { name: 'Schedule' })).toBeNull();
	});

	it('skips rounds with no games', () => {
		renderWith(
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

	it('names an unknown team and hides the results in French', () => {
		const orphan = {
			...summary,
			results: [...summary.results, { ...summary.results[0], id: 199, team: 42, ranking: 4, points: 0 }]
		};
		renderWith(Page, { data: dataFor(orphan, 10) }, 'fr');

		const rows = screen.getAllByTestId('result-row');
		expect(rows[3]).toHaveTextContent(/4\s*Inconnue/);

		renderWith(Page, { data: dataFor(summary, 11) }, 'fr');
		expect(screen.getByText('Résultats non dévoilés')).toBeInTheDocument();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: dataFor(summary, 10) }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Relais' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Programme' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Tour 1' }).parentElement).toHaveTextContent('1 à jouer');
		expect(screen.getByRole('heading', { name: 'Tour 2' }).parentElement).toHaveTextContent('1 match');
	});
});

describe('discipline page for an organiser', () => {
	it('shows nothing of it to a visitor even with a staff payload', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 11) });
		expect(screen.queryByText('Results hidden from the public')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('offers to hide a revealed discipline, with no missing count', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 10, true) }, 'en', true);
		expect(screen.getByText('Results are public')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Hide' })).toBeInTheDocument();
		expect(screen.queryByText(/to play/)).toBeNull();
	});

	it('says how many games are unplayed on a hidden discipline with games', () => {
		const hidden = { ...summaryStaff, disciplines: summaryStaff.disciplines.map((d) => (d.id === 10 ? { ...d, reveal_score: false } : d)) };
		renderWith(Page, { data: dataFor(hidden, 10, true) }, 'en', true);
		expect(screen.getByText('Results hidden from the public')).toBeInTheDocument();
		expect(screen.getAllByText('1 to play').length).toBeGreaterThan(0);
	});

	it('shows result lines with the stored values for a discipline without rounds', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 12, true) }, 'en', true);

		expect(screen.getByText('Results hidden from the public')).toBeInTheDocument();
		expect(screen.getByText('1 team without a result')).toBeInTheDocument();
		const lines = screen.getAllByTestId('result-line');
		expect(lines).toHaveLength(3);
		expect(lines[0]).toHaveTextContent('Aigles');
		expect(lines[0].querySelector('input[name="value"]')).toHaveValue(20);
		expect(lines[1].querySelector('input[name="value"]')).toHaveValue(null);
		// The testid is on the <form> itself (per the markup), so the line IS the form.
		expect(lines[0]).toHaveAttribute('action', '?/result');
		expect(lines[0].querySelector('input[name="result"]')).toHaveValue('106');
		expect(lines[0].querySelector('input[name="kind"]')).toHaveValue('PTS');
		expect(screen.queryByTestId('result-row')).toBeNull();
	});

	it('shows a time field as mm:ss for a timed discipline', () => {
		const timed = { ...summaryStaff, rounds: summaryStaff.rounds.filter((r) => r.discipline !== 11), games: summaryStaff.games.filter((g) => g.discipline !== 11) };
		renderWith(Page, { data: dataFor(timed, 11, true) }, 'en', true);

		const lines = screen.getAllByTestId('result-line');
		expect(lines[0].querySelector('input[name="value"]')).toHaveValue('12:30');
		expect(lines[0].querySelector('input[name="value"]')).toHaveAttribute('placeholder', 'mm:ss');
		expect(lines[0].querySelector('input[name="value"]')).toHaveAttribute('pattern', '[0-9]{1,3}:[0-5][0-9]');
		expect(lines[0].querySelector('input[name="value"]')).not.toHaveAttribute('inputmode');
		expect(lines[0].querySelector('input[name="kind"]')).toHaveValue('TIM');
	});

	it('turns game rows into buttons that open the sheet', async () => {
		renderWith(Page, { data: dataFor(summaryStaff, 10, true) }, 'en', true);

		const row = screen.getAllByRole('button', { name: /Cerfs\s*— : —\s*Bisons/ })[0];
		expect(screen.queryByRole('dialog')).toBeNull();
		await fireEvent.click(row);
		expect(screen.getByRole('dialog', { name: 'Round 1 · ref: Aigles' })).toBeInTheDocument();
	});

	it('offers to close a complete Swiss round only', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 11, true) }, 'en', true);
		// Orienteering is Swiss with one played game in round 1
		const close = screen.getByRole('button', { name: 'Close the round' });
		expect(close.closest('form').querySelector('input[name="round"]')).toHaveValue('22');

		const { container } = renderWith(Page, { data: dataFor(summaryStaff, 10, true) }, 'en', true);
		// Relay is round robin: never a close button, even on its complete round 2
		expect(container.querySelectorAll('form[action="?/close"]')).toHaveLength(0);
	});

	it('labels a closed round as done and hides its button', () => {
		const closed = { ...summaryStaff, rounds: summaryStaff.rounds.map((r) => (r.id === 22 ? { ...r, is_over: true } : r)) };
		renderWith(Page, { data: dataFor(closed, 11, true) }, 'en', true);
		expect(screen.queryByRole('button', { name: 'Close the round' })).toBeNull();
		expect(screen.getByRole('heading', { name: 'Round 1' }).parentElement).toHaveTextContent('Done');
	});

	it('shows the error line under the control the action names, also when form changes later', async () => {
		const { component } = renderWith(Page, { data: dataFor(summaryStaff, 12, true) }, 'en', true);
		expect(screen.queryByRole('alert')).toBeNull();

		// A failed action updates `form` without reloading `data`: the line must still appear.
		await component.$set({ form: { action: 'result', id: 107, error: 'orga.error.invalid' } });
		const lines = screen.getAllByTestId('result-line');
		expect(lines[1]).toHaveTextContent('Value refused');
		expect(lines[0]).not.toHaveTextContent('Value refused');
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 12, true) }, 'fr', true);
		expect(screen.getByText('Résultats masqués pour le public')).toBeInTheDocument();
		expect(screen.getByText('1 équipe sans résultat')).toBeInTheDocument();
		expect(screen.getAllByRole('button', { name: 'Enregistrer' })).toHaveLength(3);
	});

	it('words the round controls in French under fr', () => {
		renderWith(Page, { data: dataFor(summaryStaff, 11, true) }, 'fr', true);
		expect(screen.getByRole('button', { name: 'Clore le tour' })).toBeInTheDocument();
		expect(screen.getAllByTitle('Saisir le score').length).toBeGreaterThan(0);

		const closed = { ...summaryStaff, rounds: summaryStaff.rounds.map((r) => (r.id === 22 ? { ...r, is_over: true } : r)) };
		renderWith(Page, { data: dataFor(closed, 11, true) }, 'fr', true);
		expect(screen.getByText('Terminé')).toBeInTheDocument();
	});

	it('shows a failed score in the open sheet, hides it once dismissed, and returns focus on cancel', async () => {
		renderWith(
			Page,
			{ data: dataFor(summaryStaff, 10, true), form: { action: 'score', id: 200, error: 'orga.error.conflict' } },
			'en',
			true
		);

		const row = screen.getAllByRole('button', { name: /Bisons\s*12 : 9\s*Aigles/ })[0];
		await fireEvent.click(row);
		const dialog = screen.getByRole('dialog');
		expect(within(dialog).getByRole('alert')).toBeInTheDocument();

		await fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(row).toHaveFocus();

		// Reopening the same game after the failure was dismissed by closing must not
		// show the same stale error again.
		await fireEvent.click(row);
		expect(screen.queryByRole('alert')).toBeNull();
	});
});
