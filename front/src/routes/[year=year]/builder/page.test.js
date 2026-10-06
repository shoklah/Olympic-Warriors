import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import Page from './+page.svelte';
import { generate } from '$lib/builder/generate.js';

vi.mock('$lib/builder/generate.js', async (original) => {
	const module = await original();
	return { ...module, generate: vi.fn(module.generate) };
});

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));

const data = (over = {}) => ({ builder: { ...builderPayload, ...over } });
const goTo = (name) => fireEvent.click(screen.getByRole('button', { name }));
const propose = async () => {
	await goTo('Teams');
	await fireEvent.click(screen.getByRole('button', { name: 'Propose teams' }));
};
const teamRegions = () => screen.getAllByRole('region', { name: /^Team \d/ });

describe('team builder page', () => {
	it('shows the step progress like the registration', async () => {
		renderWith(Page, { data: data() });

		expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
		const bar = screen.getByRole('progressbar', { name: 'Builder steps' });
		expect(bar).toHaveAttribute('aria-valuenow', '1');
		expect(bar).toHaveAttribute('aria-valuemax', '3');
		await goTo('Teams');
		expect(screen.getByText('Step 2 of 3')).toBeInTheDocument();
		expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '2');
	});

	it('moves with Next and Previous and hides them at the ends', async () => {
		renderWith(Page, { data: data() });

		expect(screen.queryByRole('button', { name: 'Previous' })).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		expect(screen.getByRole('heading', { name: 'Teams' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		expect(screen.getByRole('heading', { name: 'Apply' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Next' })).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
		expect(screen.getByRole('heading', { name: 'Teams' })).toBeInTheDocument();
	});

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

	it('confirms every clear match with one click and keeps the count and the warning in step', async () => {
		renderWith(Page, { data: data() });

		expect(screen.getByText('0 confirmed')).toBeInTheDocument();
		expect(screen.getByText('4 to review')).toBeInTheDocument();
		expect(screen.getByText("4 requests aren't confirmed and will be ignored.")).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm 4 clear matches' }));

		for (const name of ['Confirm Paul Durand', 'Confirm Zoé Blanc', 'Confirm Léa Martin', 'Confirm Bob Roux']) {
			expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
		}
		expect(screen.getByText('4 confirmed')).toBeInTheDocument();
		expect(screen.getByText('0 to review')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /clear match/ })).toBeNull();
		expect(screen.queryByText(/will be ignored/)).toBeNull();
	});

	it('warns that unconfirmed requests are ignored only while some are left, and only on the requests step', async () => {
		renderWith(Page, { data: data() });
		await fireEvent.click(screen.getByRole('button', { name: 'Confirm Paul Durand' }));

		expect(screen.getByText("3 requests aren't confirmed and will be ignored.")).toBeInTheDocument();

		await goTo('Teams');
		expect(screen.queryByText(/will be ignored/)).toBeNull();
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

	it('goes stale when the apply is refused as stale, and loads the server data again', async () => {
		const { invalidateAll } = await import('$app/navigation');
		invalidateAll.mockClear();
		vi.stubGlobal('fetch', vi.fn(async (url) =>
			url.endsWith('/apply')
				? new Response(JSON.stringify({ error: 'stale_draft' }), { status: 409, headers: { 'content-type': 'application/json' } })
				: new Response(JSON.stringify({ updated_at: 'v1' }), { status: 200, headers: { 'content-type': 'application/json' } })
		));
		renderWith(Page, { data: data() });
		await propose();
		await goTo('Apply');

		await fireEvent.click(screen.getByRole('button', { name: 'Create the teams' }));
		await vi.waitFor(() => expect(screen.getByText('Someone else changed the draft.')).toBeInTheDocument());
		expect(screen.getByRole('button', { name: 'Create the teams' })).toBeDisabled();

		await fireEvent.click(screen.getByRole('button', { name: 'Load their version' }));

		expect(invalidateAll).toHaveBeenCalled();
		await vi.waitFor(() => expect(screen.queryByText('Someone else changed the draft.')).toBeNull());
		vi.unstubAllGlobals();
	});

	it('keeps saying it is saving while a newer edit waits behind the answered save', async () => {
		let release;
		vi.stubGlobal('fetch', vi.fn(() => new Promise((r) => (release = () => r(new Response(JSON.stringify({ updated_at: 'v1' }), { status: 200, headers: { 'content-type': 'application/json' } }))))));
		renderWith(Page, { data: data() });
		await propose();
		await vi.waitFor(() => expect(release).toBeDefined(), { timeout: 3000 });
		await fireEvent.click(screen.getByRole('button', { name: 'Re-roll' }));
		release();
		await new Promise((r) => setTimeout(r, 20));

		expect(screen.queryByText('Draft saved')).toBeNull();
		vi.unstubAllGlobals();
	});

	it('re-rolls with variety while proposing stays best-of', async () => {
		renderWith(Page, { data: data() });
		await propose();
		expect(generate.mock.calls.at(-1)[3].variety).toBeFalsy();

		await fireEvent.click(screen.getByRole('button', { name: 'Re-roll' }));

		expect(generate.mock.calls.at(-1)[3].variety).toBe(true);
	});

	it('keeps its save status in place: always there, with the text switching instead of appearing', async () => {
		const resolvers = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(() => new Promise((resolve) => resolvers.push(resolve)))
		);
		renderWith(Page, { data: data() });
		const status = screen.getByRole('status');

		expect(status).toBeInTheDocument();
		expect(status).toHaveTextContent('');

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm Paul Durand' }));
		expect(screen.getByRole('status')).toBe(status);
		expect(status).toHaveTextContent('Saving…');

		await vi.waitFor(() => expect(resolvers.length).toBe(1), { timeout: 3000 });
		resolvers[0]({ status: 200, ok: true, json: async () => ({ updated_at: 'v1' }) });
		await vi.waitFor(() => expect(status).toHaveTextContent('Draft saved'));
		expect(screen.getByRole('status')).toBe(status);
		vi.unstubAllGlobals();
	});

	it('opens a player sheet from the eye button and gives focus back on close', async () => {
		renderWith(Page, { data: data() });
		await goTo('Teams');

		const eye = screen.getByRole('button', { name: 'View Léa Martin profile' });
		await fireEvent.click(eye);

		const sheet = within(screen.getByRole('dialog', { name: 'Léa Martin' }));
		expect(sheet.getByText('To place')).toBeInTheDocument();
		expect(sheet.getByText('Cardio')).toBeInTheDocument();

		await fireEvent.click(sheet.getByRole('button', { name: 'Close' }));

		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.activeElement).toBe(eye);
	});

	it('names the team of a placed player in the sheet', async () => {
		renderWith(Page, { data: data() });
		await propose();

		const region = teamRegions()[0];
		await fireEvent.click(within(region).getAllByRole('button', { name: /^View .* profile$/ })[0]);

		expect(within(screen.getByRole('dialog')).getByText('Team 1')).toBeInTheDocument();
	});

	describe('compare and swap', () => {
		const openCompare = async (first, second) => {
			const region = teamRegions().find((r) => within(r).queryByText(first));
			await fireEvent.click(within(region).getByRole('button', { name: `View ${first} profile` }));
			await fireEvent.click(screen.getByRole('button', { name: 'Compare with…' }));
			await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: new RegExp(second) }));
		};

		it('swaps two players in one save, keeps the sheet on the pair, and a second swap undoes it', async () => {
			const fetchMock = vi.fn(async () => ({ status: 200, ok: true, json: async () => ({ updated_at: 'v1' }) }));
			vi.stubGlobal('fetch', fetchMock);
			renderWith(Page, { data: data() });
			await propose();
			const teams = () => teamRegions().map((r) => [...r.querySelectorAll('.name')].map((n) => n.textContent));
			const before = teams();
			const first = before[0][0];
			const second = before[1][0];

			await openCompare(first, second);
			const dialog = within(screen.getByRole('dialog'));
			expect(dialog.getByRole('table')).toBeInTheDocument();
			await fireEvent.click(dialog.getByRole('button', { name: 'Swap' }));

			const after = teams();
			expect(after[0]).toContain(second);
			expect(after[1]).toContain(first);
			expect(screen.getByRole('dialog', { name: first })).toBeInTheDocument();
			expect(dialog.getByRole('table')).toBeInTheDocument();

			await fireEvent.click(dialog.getByRole('button', { name: 'Swap' }));
			expect(teams()).toEqual(before);
			await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled(), { timeout: 3000 });
			expect(fetchMock).toHaveBeenCalledTimes(1);
			vi.unstubAllGlobals();
		});

		it('refuses to swap a locked player and says why', async () => {
			renderWith(Page, { data: data() });
			await propose();
			const region = teamRegions()[0];
			const first = region.querySelector('.name').textContent;
			const second = teamRegions()[1].querySelector('.name').textContent;
			await fireEvent.click(within(region).getAllByRole('button', { name: /^Lock / })[0]);

			await openCompare(first, second);

			const dialog = within(screen.getByRole('dialog'));
			expect(dialog.getByRole('button', { name: 'Swap' })).toBeDisabled();
			expect(dialog.getByText('A locked player cannot be swapped.')).toBeInTheDocument();
		});

		it('forgets the comparison when the sheet closes', async () => {
			renderWith(Page, { data: data() });
			await propose();
			const first = teamRegions()[0].querySelector('.name').textContent;
			await openCompare(first, teamRegions()[1].querySelector('.name').textContent);

			await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }));
			await fireEvent.click(within(teamRegions()[0]).getByRole('button', { name: `View ${first} profile` }));

			expect(within(screen.getByRole('dialog')).queryByRole('table')).toBeNull();
		});
	});

	describe('undo and redo', () => {
		const undoButton = () => screen.getByRole('button', { name: 'Undo' });
		const redoButton = () => screen.getByRole('button', { name: 'Redo' });
		const names = () => teamRegions().map((r) => [...r.querySelectorAll('.name')].map((n) => n.textContent));

		it('starts with both buttons disabled', async () => {
			renderWith(Page, { data: data() });
			await goTo('Teams');

			expect(undoButton()).toBeDisabled();
			expect(redoButton()).toBeDisabled();
		});

		it('undoes and redoes a proposal and a move', async () => {
			renderWith(Page, { data: data() });
			await propose();
			const proposed = names();
			const card = within(teamRegions()[0]).getAllByRole('listitem')[0];
			await fireEvent.change(within(card).getByRole('combobox'), { target: { value: '1' } });
			const moved = names();
			expect(moved).not.toEqual(proposed);

			await fireEvent.click(undoButton());
			expect(names()).toEqual(proposed);
			expect(redoButton()).toBeEnabled();

			await fireEvent.click(undoButton());
			expect(screen.queryAllByRole('region', { name: /^Team \d/ })).toHaveLength(0);
			expect(undoButton()).toBeDisabled();

			await fireEvent.click(redoButton());
			await fireEvent.click(redoButton());
			expect(names()).toEqual(moved);
			expect(redoButton()).toBeDisabled();
		});

		it('forgets what can be redone after a new edit', async () => {
			renderWith(Page, { data: data() });
			await propose();
			await fireEvent.click(undoButton());
			await propose();

			expect(redoButton()).toBeDisabled();
		});

		it('answers Ctrl+Z and Ctrl+Shift+Z, but not inside a text field', async () => {
			renderWith(Page, { data: data() });
			await propose();

			const field = screen.getByLabelText('Players per team');
			await fireEvent.keyDown(field, { key: 'z', ctrlKey: true });
			expect(teamRegions().length).toBeGreaterThan(0);

			await fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
			expect(screen.queryAllByRole('region', { name: /^Team \d/ })).toHaveLength(0);
			await fireEvent.keyDown(window, { key: 'z', metaKey: true, shiftKey: true });
			expect(teamRegions().length).toBeGreaterThan(0);
		});

		it('makes the team-size field one step however many keystrokes it took', async () => {
			renderWith(Page, { data: data() });
			await goTo('Teams');
			const field = screen.getByLabelText('Players per team');

			for (const value of ['4', '5']) await fireEvent.change(field, { target: { value } });
			await fireEvent.click(undoButton());

			expect(screen.getByLabelText('Players per team')).toHaveValue(3);
			expect(undoButton()).toBeDisabled();
		});

		it('ignores the shortcut while the player sheet is open', async () => {
			renderWith(Page, { data: data() });
			await propose();
			await fireEvent.click(within(teamRegions()[0]).getAllByRole('button', { name: /^View .* profile$/ })[0]);

			await fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
			expect(undoButton()).toBeEnabled();
			expect(screen.getByRole('dialog')).toBeInTheDocument();
		});
	});
});
