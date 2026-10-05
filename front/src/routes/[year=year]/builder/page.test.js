import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));

const data = (over = {}) => ({ builder: { ...builderPayload, ...over } });
const goTo = (name) => fireEvent.click(screen.getByRole('button', { name }));
const propose = async () => {
	await goTo('Teams');
	await fireEvent.click(screen.getByRole('button', { name: 'Propose teams' }));
};
const teamRegions = () => screen.getAllByRole('region', { name: /^Team \d/ });

describe('team builder page', () => {
	it('opens on the requests with the matches proposed from the free text', () => {
		renderWith(Page, { data: data() });

		expect(screen.getByRole('heading', { name: 'Requests' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Confirm Paul Durand' })).toHaveAttribute('aria-pressed', 'false');
	});

	it('confirms a link by its button and shows it as pressed', async () => {
		renderWith(Page, { data: data() });

		const button = screen.getByRole('button', { name: 'Confirm Paul Durand' });
		await fireEvent.click(button);

		expect(button).toHaveAttribute('aria-pressed', 'true');
	});

	it('proposes teams, placing every player and flagging an incomplete profile', async () => {
		renderWith(Page, { data: data() });

		await propose();

		expect(teamRegions()).toHaveLength(2);
		expect(screen.queryByText('To place')).toBeNull();
		expect(teamRegions().flatMap((r) => within(r).getAllByRole('listitem'))).toHaveLength(6);
		expect(screen.getByText('Incomplete profile')).toBeInTheDocument(); // Bob has no ratings
	});

	it('fixes the players-per-team number once teams are proposed, until everything is reset', async () => {
		renderWith(Page, { data: data() });
		await propose();

		expect(screen.getByLabelText('Players per team')).toBeDisabled();

		vi.spyOn(window, 'confirm').mockReturnValue(true);
		await fireEvent.click(screen.getByRole('button', { name: 'Reset everything' }));

		expect(screen.getByLabelText('Players per team')).toBeEnabled();
		expect(screen.getByText('To place')).toBeInTheDocument();
	});

	it('moves a player to another team from the menu', async () => {
		renderWith(Page, { data: data() });
		await propose();
		const [first, second] = teamRegions();
		const card = within(first).getAllByRole('listitem')[0];
		const name = card.querySelector('.name').textContent;

		await fireEvent.change(within(card).getByRole('combobox'), { target: { value: '1' } });

		expect(within(teamRegions()[1]).getByText(name)).toBeInTheDocument();
		expect(within(teamRegions()[0]).queryByText(name)).toBeNull();
	});

	it('locks a player', async () => {
		renderWith(Page, { data: data() });
		await propose();

		const lock = screen.getAllByRole('button', { name: /^Lock / })[0];
		await fireEvent.click(lock);

		expect(screen.getAllByRole('button', { name: /^Unlock / })).toHaveLength(1);
	});

	it('shows only a message and no builder when teams already exist', () => {
		renderWith(Page, { data: data({ teams_exist: true }) });

		expect(screen.getByText(/already has teams/)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Propose teams' })).toBeNull();
	});

	it('keeps Apply disabled while a player is unplaced, and says the teams become public', async () => {
		renderWith(Page, { data: data() });
		await goTo('Apply');

		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();
		expect(screen.getByText(/public as soon as they are created/)).toBeInTheDocument();
	});

	it('asks for a confirmation while registration is open', async () => {
		renderWith(Page, { data: data({ registration_open: true }) });
		await propose();
		await goTo('Apply');

		expect(screen.getByText(/still open/)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();

		await fireEvent.click(screen.getByLabelText('I create the teams anyway'));

		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeEnabled();
	});

	it('applies through the page endpoint and lists the disciplines still to schedule', async () => {
		const fetch = vi.fn(async () =>
			new Response(JSON.stringify({ teams: [], unscheduled: [{ id: 3, name: 'Darts' }] }), { status: 200, headers: { 'content-type': 'application/json' } })
		);
		vi.stubGlobal('fetch', fetch);
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));
		await vi.waitFor(() => expect(screen.getByText('Teams created.')).toBeInTheDocument());

		expect(fetch.mock.calls.at(-1)[0]).toBe('/2029/builder/apply');
		expect(screen.getByText('Darts')).toBeInTheDocument();
		vi.unstubAllGlobals();
	});

	it('sends the version it saved with the apply, and refreshes the layout data', async () => {
		const { invalidateAll } = await import('$app/navigation');
		const fetch = vi.fn(async (url) =>
			new Response(JSON.stringify(url.endsWith('/apply') ? { teams: [], unscheduled: [] } : { updated_at: 'v7' }), { status: 200, headers: { 'content-type': 'application/json' } })
		);
		vi.stubGlobal('fetch', fetch);
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));
		await vi.waitFor(() => expect(screen.getByText('Teams created.')).toBeInTheDocument());

		const call = fetch.mock.calls.find(([url]) => url.endsWith('/apply'));
		expect(JSON.parse(call[1].body)).toEqual({ based_on: 'v7' });
		expect(invalidateAll).toHaveBeenCalled();
		vi.unstubAllGlobals();
	});

	it('disables Apply while the draft is stale', async () => {
		vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'stale_draft', draft: null }), { status: 409, headers: { 'content-type': 'application/json' } })));
		renderWith(Page, { data: data() });
		await propose();
		await vi.waitFor(() => expect(screen.getByText("Someone else changed the draft.")).toBeInTheDocument(), { timeout: 3000 });
		await goTo('Apply');

		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();
		vi.unstubAllGlobals();
	});

	it('shows the request notes by default and hides them from the switch, remembering it', async () => {
		localStorage.clear();
		renderWith(Page, { data: data() });
		await propose();

		expect(screen.getAllByText('+ Paul Durand').length).toBeGreaterThan(0);

		await fireEvent.click(screen.getByLabelText('Show the requests on the cards'));

		expect(screen.queryByText('+ Paul Durand')).toBeNull();
		expect(localStorage.getItem('builder.showRequests')).toBe('off');
	});

	it('starts with the notes hidden when the browser remembers that', async () => {
		localStorage.setItem('builder.showRequests', 'off');
		renderWith(Page, { data: data() });
		await propose();

		expect(screen.queryByText('+ Paul Durand')).toBeNull();
		expect(screen.getByLabelText('Show the requests on the cards')).not.toBeChecked();
		localStorage.clear();
	});

	it('words an apply refusal', async () => {
		vi.stubGlobal('fetch', vi.fn(async (url) =>
			url.endsWith('/apply')
				? new Response(JSON.stringify({ error: 'teams_exist' }), { status: 409, headers: { 'content-type': 'application/json' } })
				: new Response(JSON.stringify({ updated_at: 'v1' }), { status: 200, headers: { 'content-type': 'application/json' } })
		));
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));

		await vi.waitFor(() => expect(screen.getByText('This edition already has teams.')).toBeInTheDocument());
		vi.unstubAllGlobals();
	});

	it('reconciles a saved draft: a departed player leaves and late registrants wait in the tray', async () => {
		const draft = {
			document: { players_per_team: 3, seed: 1, links: [], locked: [], teams: [{ players: [1, 2, 3] }, { players: [4, 99] }] },
			updated_at: 'v1'
		};
		renderWith(Page, { data: data({ draft }) });
		await goTo('Teams');

		expect(screen.getByText('2 new registrants to place')).toBeInTheDocument();
		expect(screen.getByText('1 withdrawal removed from the teams')).toBeInTheDocument();
		expect(screen.getByText('To place')).toBeInTheDocument();
	});

	it('places the newcomers without moving anyone', async () => {
		const draft = {
			document: { players_per_team: 3, seed: 1, links: [], locked: [], teams: [{ players: [1, 2, 3] }, { players: [4] }] },
			updated_at: 'v1'
		};
		renderWith(Page, { data: data({ draft }) });
		await goTo('Teams');
		const before = teamRegions().map((r) => within(r).getAllByRole('listitem').map((li) => li.querySelector('.name').textContent));

		await fireEvent.click(screen.getByRole('button', { name: 'Place the newcomers' }));

		expect(screen.queryByText('To place')).toBeNull();
		const after = teamRegions().map((r) => within(r).getAllByRole('listitem').map((li) => li.querySelector('.name').textContent));
		before.forEach((names, i) => names.forEach((n) => expect(after[i]).toContain(n)));
		expect(after.flat()).toHaveLength(6);
	});

	it('speaks French', () => {
		renderWith(Page, { data: data() }, 'fr');

		expect(screen.getByRole('heading', { name: 'Demandes' })).toBeInTheDocument();
	});
});
