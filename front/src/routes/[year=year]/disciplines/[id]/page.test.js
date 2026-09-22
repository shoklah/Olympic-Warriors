import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { disciplineResults, findDiscipline } from '$lib/edition';
import { summary, summaryAllRevealed } from '$lib/fixtures/summary.js';

const dataFor = (s, id) => ({
	summary: s,
	discipline: findDiscipline(s, id),
	results: disciplineResults(s, id)
});

describe('discipline page', () => {
	it('shows points rows with the difference for a revealed points discipline', () => {
		render(Page, { data: dataFor(summary, 10) });

		expect(screen.getByRole('heading', { name: 'Relay' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('result-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/1\.\s*Bisons\s*10 pts \(\+4\)/);
		expect(rows[1]).toHaveTextContent(/2\.\s*Aigles\s*5 pts \(-2\)/);
		expect(rows[2]).toHaveTextContent(/3\.\s*Cerfs\s*0 pts \(-2\)/);
		expect(screen.getByRole('link', { name: 'Bisons' })).toHaveAttribute('href', '/2026/teams/2');
	});

	it('shows times for a revealed timed discipline', () => {
		render(Page, { data: dataFor(summaryAllRevealed, 11) });

		const rows = screen.getAllByTestId('result-row');
		expect(rows[0]).toHaveTextContent('1. Aigles');
		expect(rows[0]).toHaveTextContent('00:12:30');
	});

	it('shows the not-revealed message instead of rows', () => {
		render(Page, { data: dataFor(summary, 11) });

		expect(screen.getByText('Results not revealed yet')).toBeInTheDocument();
		expect(screen.queryAllByTestId('result-row')).toHaveLength(0);
	});
});
