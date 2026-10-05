import { fireEvent, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import BuilderApply from './BuilderApply.svelte';

const base = { teamCount: 2, placedCount: 6, unplacedCount: 0, registrationOpen: false, nameOf: (id) => `P${id}` };
const button = () => screen.getByRole('button', { name: 'Create the teams' });

describe('BuilderApply', () => {
	it('is enabled when everything is placed and registration is closed', () => {
		renderWith(BuilderApply, base);

		expect(button()).toBeEnabled();
	});

	it.each([
		['no team', { teamCount: 0 }],
		['an unplaced player', { unplacedCount: 1 }],
		['a stale or failing draft', { saveBlocked: true }],
		['a request in flight', { busy: true }]
	])('is disabled with %s', (_, over) => {
		renderWith(BuilderApply, { ...base, ...over });

		expect(button()).toBeDisabled();
	});

	it('asks to confirm while registration is open', async () => {
		renderWith(BuilderApply, { ...base, registrationOpen: true });
		expect(button()).toBeDisabled();

		await fireEvent.click(screen.getByLabelText('I create the teams anyway'));

		expect(button()).toBeEnabled();
	});

	it('lists the unmet requests', () => {
		renderWith(BuilderApply, { ...base, unmet: [{ kind: 'with', player: 1, target: 2, mutual: true }] });

		expect(screen.getByText('P1 wanted to be with P2 (mutual)')).toBeInTheDocument();
	});

	it('words an error', () => {
		renderWith(BuilderApply, { ...base, error: 'builder.error.teams_exist' });

		expect(screen.getByRole('alert')).toHaveTextContent('This edition already has teams.');
	});

	it('lists the disciplines still to schedule once done', () => {
		renderWith(BuilderApply, { ...base, done: { teams: [], unscheduled: [{ id: 3, name: 'Darts' }] } });

		expect(screen.getByText('Teams created.')).toBeInTheDocument();
		expect(screen.getByText('Darts')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Create the teams' })).toBeNull();
	});

	it('links to the announcement visuals once the teams are created', () => {
		renderWith(BuilderApply, { ...base, year: 2029, done: { teams: [{ id: 1 }], unscheduled: [] } });

		expect(screen.getByRole('link', { name: 'Announce the teams' })).toHaveAttribute('href', '/2029/announce');
	});
});
