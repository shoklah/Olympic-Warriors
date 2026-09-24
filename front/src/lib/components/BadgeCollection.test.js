import { fireEvent, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { badgeCollection } from '$lib/badges';
import BadgeCollection from './BadgeCollection.svelte';

/**
 * A stand-in for use:enhance that runs the component's submit function and callback the way
 * SvelteKit does, without a network: `posted` records each form sent (its action and its
 * `codes` in order), `result` is what the action answers (a promise a test can hold back to
 * see the busy state), and `updates` records the options of every update() call.
 */
const forms = vi.hoisted(() => ({ posted: [], result: null, updates: [] }));

vi.mock('$app/forms', () => ({
	enhance(form, submit = () => {}) {
		async function onSubmit(event) {
			event.preventDefault();
			let cancelled = false;
			const formData = new FormData(form);
			const callback = await submit({
				formData,
				formElement: form,
				submitter: event.submitter,
				cancel: () => {
					cancelled = true;
				}
			});
			if (cancelled) return;
			forms.posted.push({ action: form.getAttribute('action'), codes: formData.getAll('codes') });
			const result = await forms.result;
			await callback?.({ result, formData, formElement: form, update: async (opts) => forms.updates.push(opts) });
		}
		form.addEventListener('submit', onSubmit);
		return { destroy: () => form.removeEventListener('submit', onSubmit) };
	}
}));

const badges = [
	{ code: 'champion', tier: 0, years: [2021, 2024], discipline: null, partner: null },
	{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null },
	{ code: 'specialist', tier: 1, years: [2026], discipline: 'Relay', partner: null },
	{
		code: 'comrades',
		tier: 0,
		years: [2026],
		discipline: null,
		partner: { id: 12, first_name: 'Léa', last_name: 'Martin' }
	},
	{ code: 'future-badge', tier: 0, years: [2026], discipline: null, partner: null }
];

/** BadgeCollection now takes the already-computed collection, like the profile page passes it. */
const renderCollection = (list, locale = 'en') => renderWith(BadgeCollection, { collection: badgeCollection(list) }, locale);

describe('BadgeCollection', () => {
	it('has a visually hidden "Badges" heading above the progress line', () => {
		renderCollection(badges);
		expect(screen.getByRole('heading', { level: 2, name: 'Badges' })).toBeInTheDocument();
	});

	it('shows the overall progress and the per-family counts', () => {
		renderCollection(badges);
		expect(screen.getByText('4 badges out of 61')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Podiums 1 of 5' })).toHaveTextContent('1/5');
		expect(screen.getByRole('heading', { name: 'Loyalty 1 of 5' })).toHaveTextContent('1/5');
		expect(screen.getByRole('heading', { name: 'Teammates 1 of 2' })).toHaveTextContent('1/2');
	});

	it('pluralises the overall progress line: 0, 1 and 2+', () => {
		renderCollection([]);
		expect(screen.getByText('0 badges out of 61')).toBeInTheDocument();

		renderCollection([{ code: 'champion', tier: 0, years: [2026], discipline: null, partner: null }]);
		expect(screen.getByText('1 badge out of 61')).toBeInTheDocument();

		renderCollection(badges);
		expect(screen.getByText('4 badges out of 61')).toBeInTheDocument();
	});

	it('renders every catalogue code as a slot button', () => {
		renderCollection(badges);
		expect(screen.getAllByRole('button')).toHaveLength(61);
	});

	it('names an earned-once slot without a count, and a locked slot without one either', () => {
		renderCollection(badges);
		expect(screen.getByRole('button', { name: 'Veteran, badge earned' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Wooden spoon, badge locked' })).toBeInTheDocument();
	});

	it('names a repeated slot with a spoken count, not "×N", and still shows the ×N chip', () => {
		renderCollection(badges);
		const champion = screen.getByRole('button', { name: 'Champion, badge earned 2 times' });
		expect(champion).toHaveTextContent('×2');
	});

	it('opens a sheet on click, named after the badge, with the entry detail and next tier', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Veteran/ }));

		const dialog = screen.getByRole('dialog', { name: 'Veteran' });
		expect(within(dialog).getByText('Badge earned')).toBeInTheDocument();
		expect(dialog).toHaveTextContent('Play 3, 5, then 10 editions');
		expect(dialog).toHaveTextContent('Tier 1');
		expect(dialog).toHaveTextContent('2026');
		expect(dialog).toHaveTextContent('Next tier: 5 editions');
	});

	it('shows the partner link of a comrades entry first', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Comrades in arms/ }));

		const link = screen.getByRole('link', { name: 'Léa Martin' });
		expect(link).toHaveAttribute('href', '/players/12');
	});

	it('shows the first tier goal of a locked tiered slot', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Networker/ }));

		const dialog = screen.getByRole('dialog', { name: 'Networker' });
		expect(within(dialog).getByText('Badge locked')).toBeInTheDocument();
		expect(dialog).toHaveTextContent('First tier: 5 teammates');
	});

	it('shows the top-tier line for a badge at tier 3', async () => {
		renderCollection([{ code: 'veteran', tier: 3, years: [2020, 2022, 2027], discipline: null, partner: null }]);
		await fireEvent.click(screen.getByRole('button', { name: /^Veteran/ }));

		expect(screen.getByRole('dialog', { name: 'Veteran' })).toHaveTextContent('Top tier');
	});

	it('closes on Escape and gives focus back to the slot button', async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);
		expect(screen.getByRole('dialog')).toBeInTheDocument();

		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('closes on a backdrop click and gives focus back to the slot button', async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);

		await fireEvent.click(screen.getByTestId('backdrop'));
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('closes on the close button and gives focus back to the slot button', async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);

		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(trigger).toHaveFocus();
	});

	it('speaks French', async () => {
		renderCollection(badges, 'fr');
		expect(screen.getByRole('heading', { level: 2, name: 'Badges' })).toBeInTheDocument();
		expect(screen.getByText('4 badges sur 61')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Palmarès 1 sur 5' })).toHaveTextContent('1/5');
		expect(screen.getByRole('button', { name: 'Cuillère de bois, badge à débloquer' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Champion, badge obtenu 2 fois' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /^Vétéran/ }));
		expect(screen.getByRole('dialog', { name: 'Vétéran' })).toHaveTextContent('Prochain niveau : 5 éditions');
	});

	it('speaks French for the 0-badge singular', () => {
		renderCollection([], 'fr');
		expect(screen.getByText('0 badge sur 61')).toBeInTheDocument();
	});

	it('gives every slot the rule as its accessible description, for every device', () => {
		renderCollection(badges);
		expect(screen.getByRole('button', { name: /^Champion/ })).toHaveAccessibleDescription('Win an edition');
		expect(screen.getByRole('button', { name: /^Wooden spoon/ })).toHaveAccessibleDescription(
			'Finish last in an edition of 4 teams or more'
		);
	});

	it('speaks the description in French too', () => {
		renderCollection(badges, 'fr');
		expect(screen.getByRole('button', { name: /^Champion/ })).toHaveAccessibleDescription('Gagner une édition');
	});

	it('hides a shown tooltip on Escape even when it is only hovered, without moving focus, and shows it again once the pointer leaves', async () => {
		renderCollection(badges);
		document.body.focus(); // nothing focused: only hover can be showing the tooltip
		const champion = screen.getByRole('button', { name: /^Champion/ });

		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('tooltip-shown');

		// The keydown listener lives on window, not on the (unfocused) slot button: a
		// hover-only tooltip has no element with focus to dispatch on.
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(champion).not.toHaveClass('tooltip-shown');
		expect(champion).not.toHaveFocus();
		expect(document.body).toHaveFocus();

		await fireEvent.mouseLeave(champion);
		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('tooltip-shown');
	});

	it('keeps a tooltip dismissed while either hover or focus remains, only resetting once both are gone', async () => {
		renderCollection(badges);
		const champion = screen.getByRole('button', { name: /^Champion/ });

		champion.focus();
		await fireEvent.mouseEnter(champion);
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(champion).not.toHaveClass('tooltip-shown');

		// The pointer leaves, but focus is still on the slot: still dismissed, not reshown.
		await fireEvent.mouseLeave(champion);
		expect(champion).not.toHaveClass('tooltip-shown');

		// Focus leaves too: only now does the dismissal clear.
		await fireEvent.blur(champion);
		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('tooltip-shown');
	});

	it("shows only the hovered slot's tooltip, even while another slot keeps keyboard focus", async () => {
		renderCollection(badges);
		const champion = screen.getByRole('button', { name: /^Champion/ });
		const veteran = screen.getByRole('button', { name: /^Veteran/ });

		await fireEvent.focus(champion);
		expect(champion).toHaveClass('tooltip-shown');

		await fireEvent.mouseEnter(veteran);
		expect(veteran).toHaveClass('tooltip-shown');
		expect(champion).not.toHaveClass('tooltip-shown');
	});

	it("treats focus returned from the closed sheet as dismissed, so its tooltip doesn't pop back up", async () => {
		renderCollection(badges);
		const trigger = screen.getByRole('button', { name: /^Veteran/ });
		await fireEvent.click(trigger);
		await fireEvent.keyDown(window, { key: 'Escape' }); // closes the sheet, returns focus

		expect(trigger).toHaveFocus();
		expect(trigger).not.toHaveClass('tooltip-shown');
	});

	it("threads badge_stats through to the sheet's rarity line", async () => {
		const badgeStats = { players: 47, holders: { champion: 12 } };
		renderWith(BadgeCollection, { collection: badgeCollection(badges), badgeStats });
		await fireEvent.click(screen.getByRole('button', { name: /^Champion/ }));

		expect(screen.getByRole('dialog', { name: 'Champion' })).toHaveTextContent(
			'26% of players have it (12 of 47)'
		);
	});

	it('shows no rarity line without badge_stats', async () => {
		renderCollection(badges);
		await fireEvent.click(screen.getByRole('button', { name: /^Champion/ }));

		expect(screen.getByRole('dialog', { name: 'Champion' })).not.toHaveTextContent('of players');
	});

	it('aligns the tooltip to the near edge for a slot close to the viewport edge, centred otherwise, off document.documentElement.clientWidth (excludes a classic scrollbar, unlike window.innerWidth)', async () => {
		renderCollection(badges);
		// jsdom gives clientWidth 0 by default (no real layout): stand in for a 1024px
		// content width, as document.documentElement.clientWidth would report with a
		// classic scrollbar eating into a 1024px window.innerWidth.
		Object.defineProperty(document.documentElement, 'clientWidth', { value: 1024, configurable: true });

		const champion = screen.getByRole('button', { name: /^Champion/ });
		vi.spyOn(champion, 'getBoundingClientRect').mockReturnValue({ left: 5, width: 70, right: 75 });
		await fireEvent.mouseEnter(champion);
		expect(champion).toHaveClass('align-left');
		expect(champion).not.toHaveClass('align-right');

		const woodenSpoon = screen.getByRole('button', { name: /^Wooden spoon/ });
		vi.spyOn(woodenSpoon, 'getBoundingClientRect').mockReturnValue({ left: 954, width: 70, right: 1024 });
		await fireEvent.mouseEnter(woodenSpoon);
		expect(woodenSpoon).toHaveClass('align-right');
		expect(woodenSpoon).not.toHaveClass('align-left');

		const veteran = screen.getByRole('button', { name: /^Veteran/ });
		vi.spyOn(veteran, 'getBoundingClientRect').mockReturnValue({ left: 477, width: 70, right: 547 });
		await fireEvent.mouseEnter(veteran);
		expect(veteran).not.toHaveClass('align-left');
		expect(veteran).not.toHaveClass('align-right');
	});
});

describe('BadgeCollection showcase selection (the owner)', () => {
	/** Earned: champion (twice), veteran, specialist, comrades; the rest locked. */
	const renderOwner = (showcase = { auto: true, badges: [] }, locale = 'en', list = badges) =>
		renderWith(BadgeCollection, { collection: badgeCollection(list), editable: true, showcase }, locale);
	const pinned = {
		auto: false,
		badges: [
			{ code: 'veteran', tier: 1, discipline: null },
			{ code: 'champion', tier: 0, discipline: null }
		]
	};

	const choose = () => screen.getByRole('button', { name: 'Choose my showcase' });
	const slot = (name) => screen.getByRole('button', { name: new RegExp(`^${name},`) });
	/** The pick order a slot shows, or null. */
	const order = (button) => within(button).queryByTestId('order')?.textContent ?? null;
	const pressed = () =>
		screen
			.getAllByRole('button', { pressed: true })
			.map((button) => [button.getAttribute('aria-label'), order(button)]);

	beforeEach(() => {
		forms.posted = [];
		forms.updates = [];
		forms.result = { type: 'success', status: 200 };
		document.body.focus();
	});

	it('is not offered without editable, and offered to the owner otherwise', () => {
		const { unmount } = renderCollection(badges);
		expect(screen.queryByRole('button', { name: 'Choose my showcase' })).toBeNull();
		unmount();

		renderOwner();
		expect(choose()).toBeInTheDocument();
		// Outside the mode the slots stay the plain buttons opening the sheet.
		expect(slot('Veteran')).not.toHaveAttribute('aria-pressed');
		expect(slot('Wooden spoon')).toBeEnabled();
	});

	it('is not offered to an owner without an earned badge: nothing to choose from', () => {
		renderOwner(undefined, 'en', []);
		expect(screen.queryByRole('button', { name: 'Choose my showcase' })).toBeNull();
	});

	it('turns earned slots into toggles and disables locked ones, the intro taking focus', async () => {
		renderOwner();
		await fireEvent.click(choose());

		expect(screen.queryByRole('button', { name: 'Choose my showcase' })).toBeNull();
		expect(screen.getByText('Pick up to 3 badges, in the order to show them.')).toHaveFocus();
		expect(slot('Veteran')).toHaveAttribute('aria-pressed', 'false');
		expect(slot('Champion')).toHaveAttribute('aria-pressed', 'false');
		expect(slot('Wooden spoon')).toBeDisabled();
		expect(slot('Wooden spoon')).not.toHaveAttribute('aria-pressed');
		expect(screen.getByRole('status')).toHaveTextContent('0 badges chosen out of 3');
	});

	it('starts empty when the showcase is automatic, whatever it shows', async () => {
		renderOwner({ auto: true, badges: pinned.badges });
		await fireEvent.click(choose());

		expect(screen.queryAllByRole('button', { pressed: true })).toHaveLength(0);
	});

	it('starts from the pins, in pin order, leaving out one no longer earned', async () => {
		renderOwner({ auto: false, badges: [...pinned.badges, { code: 'rookie', tier: 0, discipline: null }] });
		await fireEvent.click(choose());

		expect(pressed()).toEqual([
			['Champion, badge earned 2 times', '2'],
			['Veteran, badge earned', '1']
		]);
		expect(screen.getByRole('status')).toHaveTextContent('2 badges chosen out of 3');
	});

	it('numbers the picks in pick order, and renumbers when one is taken back', async () => {
		renderOwner();
		await fireEvent.click(choose());

		await fireEvent.click(slot('Specialist'));
		await fireEvent.click(slot('Champion'));
		await fireEvent.click(slot('Veteran'));
		expect(order(slot('Specialist'))).toBe('1');
		expect(order(slot('Champion'))).toBe('2');
		expect(order(slot('Veteran'))).toBe('3');
		expect(slot('Champion')).toHaveAccessibleDescription('Place 2 in the showcase. Win an edition');

		await fireEvent.click(slot('Specialist'));
		expect(slot('Specialist')).toHaveAttribute('aria-pressed', 'false');
		expect(order(slot('Specialist'))).toBeNull();
		expect(slot('Specialist')).toHaveAccessibleDescription(expect.not.stringContaining('Place'));
		expect(order(slot('Champion'))).toBe('1');
		expect(order(slot('Veteran'))).toBe('2');
	});

	it('toggles instead of opening the sheet, and ignores a click on a locked slot', async () => {
		renderOwner();
		await fireEvent.click(choose());

		await fireEvent.click(slot('Veteran'));
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(slot('Veteran')).toHaveAttribute('aria-pressed', 'true');

		await fireEvent.click(slot('Wooden spoon'));
		expect(screen.getByRole('status')).toHaveTextContent('1 badge chosen out of 3');
	});

	it('refuses a fourth pick with a polite status line, which clears on the next change', async () => {
		renderOwner();
		await fireEvent.click(choose());
		for (const name of ['Champion', 'Veteran', 'Specialist']) await fireEvent.click(slot(name));

		await fireEvent.click(slot('Comrades in arms'));
		expect(slot('Comrades in arms')).toHaveAttribute('aria-pressed', 'false');
		expect(screen.getByRole('status')).toHaveTextContent('3 badges at most');
		expect(screen.queryByRole('alert')).toBeNull();

		await fireEvent.click(slot('Veteran'));
		expect(screen.getByRole('status')).toHaveTextContent('2 badges chosen out of 3');
		await fireEvent.click(slot('Comrades in arms'));
		expect(order(slot('Comrades in arms'))).toBe('3');
	});

	it('cancels without a request, restoring the pins, focus back on the choose button', async () => {
		renderOwner(pinned);
		await fireEvent.click(choose());
		await fireEvent.click(slot('Veteran'));
		await fireEvent.click(slot('Specialist'));

		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		expect(forms.posted).toEqual([]);
		expect(screen.queryAllByRole('button', { pressed: false })).toHaveLength(0);
		await waitFor(() => expect(choose()).toHaveFocus());

		await fireEvent.click(choose());
		expect(pressed()).toEqual([
			['Champion, badge earned 2 times', '2'],
			['Veteran, badge earned', '1']
		]);
	});

	it('saves the picks in order through the form, then reloads and gives focus back', async () => {
		renderOwner();
		await fireEvent.click(choose());
		await fireEvent.click(slot('Specialist'));
		await fireEvent.click(slot('Champion'));

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(choose()).toHaveFocus());
		expect(forms.posted).toEqual([{ action: '?/showcase', codes: ['specialist', 'champion'] }]);
		expect(forms.updates).toEqual([{ reset: false }]);
		expect(screen.queryAllByRole('button', { pressed: false })).toHaveLength(0);
	});

	it('saves an empty selection as no code at all', async () => {
		renderOwner(pinned);
		await fireEvent.click(choose());
		await fireEvent.click(slot('Veteran'));
		await fireEvent.click(slot('Champion'));

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(forms.posted).toEqual([{ action: '?/showcase', codes: [] }]));
	});

	it('offers « Back to automatic » over pins only, posting no code', async () => {
		const { unmount } = renderOwner();
		await fireEvent.click(choose());
		expect(screen.queryByRole('button', { name: 'Back to automatic' })).toBeNull();
		unmount();

		renderOwner(pinned);
		await fireEvent.click(choose());
		await fireEvent.click(screen.getByRole('button', { name: 'Back to automatic' }));
		await waitFor(() => expect(choose()).toHaveFocus());
		expect(forms.posted).toEqual([{ action: '?/showcase', codes: [] }]);
		expect(forms.updates).toEqual([{ reset: false }]);
	});

	it('holds every control while saving, and sends nothing twice', async () => {
		let answer;
		forms.result = new Promise((resolve) => (answer = resolve));
		renderOwner(pinned);
		await fireEvent.click(choose());

		const save = screen.getByRole('button', { name: 'Save' });
		await fireEvent.click(save);
		await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Saving…'));
		expect(save).toHaveAttribute('aria-disabled', 'true');
		expect(screen.getByRole('button', { name: 'Back to automatic' })).toHaveAttribute('aria-disabled', 'true');
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
		expect(slot('Veteran')).toHaveAttribute('aria-disabled', 'true');

		await fireEvent.click(slot('Veteran'));
		expect(slot('Veteran')).toHaveAttribute('aria-pressed', 'true');
		await fireEvent.click(save);
		expect(forms.posted).toHaveLength(1);

		answer({ type: 'success', status: 200 });
		await waitFor(() => expect(choose()).toHaveFocus());
	});

	it('stays in the mode with an alert when the action fails, the picks kept', async () => {
		forms.result = { type: 'failure', status: 400, data: { action: 'showcase', error: 'showcase.error.invalid' } };
		renderOwner();
		await fireEvent.click(choose());
		await fireEvent.click(slot('Veteran'));

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() =>
			expect(screen.getByRole('alert')).toHaveTextContent('This selection was refused: reload the page and try again')
		);
		expect(slot('Veteran')).toHaveAttribute('aria-pressed', 'true');
		expect(screen.getByRole('button', { name: 'Save' })).not.toHaveAttribute('aria-disabled');
		expect(forms.updates).toEqual([]);
	});

	it('words a thrown error or a stray answer as a plain failure, without applying it', async () => {
		forms.result = { type: 'error', status: 500, error: new Error('boom') };
		renderOwner();
		await fireEvent.click(choose());

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('The change failed: try again later'));
		expect(forms.updates).toEqual([]);

		forms.result = { type: 'failure', status: 403, data: { error: 'photo.error.forbidden' } };
		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(forms.posted).toHaveLength(2));
		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('The change failed: try again later'));
	});

	it("ends the mode when the page stops being the owner's, or has nothing left to choose", async () => {
		const { component } = renderOwner();
		await fireEvent.click(choose());
		expect(slot('Veteran')).toHaveAttribute('aria-pressed', 'false');

		await component.$set({ editable: false });
		expect(slot('Veteran')).not.toHaveAttribute('aria-pressed');
		expect(screen.queryByRole('status')).toBeNull();

		await component.$set({ editable: true });
		await fireEvent.click(choose());
		await component.$set({ collection: badgeCollection([]) });
		expect(screen.queryByRole('status')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
	});

	it('speaks French', async () => {
		renderOwner(pinned, 'fr');
		await fireEvent.click(screen.getByRole('button', { name: 'Choisir ma vitrine' }));

		expect(screen.getByText("Choisissez jusqu'à 3 badges, dans l'ordre où les montrer.")).toHaveFocus();
		expect(screen.getByRole('status')).toHaveTextContent('2 badges choisis sur 3');
		expect(screen.getByRole('button', { name: 'Vétéran, badge obtenu' })).toHaveAccessibleDescription(
			'Place 1 dans la vitrine. Jouer 3, 5 puis 10 éditions'
		);
		await fireEvent.click(screen.getByRole('button', { name: /^Spécialiste,/ }));
		await fireEvent.click(screen.getByRole('button', { name: /^Compagnons d'armes,/ }));
		expect(screen.getByRole('status')).toHaveTextContent('3 badges maximum');
		expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Annuler' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: "Revenir à l'automatique" })).toBeInTheDocument();
	});

	it('speaks French for no pick and one, 0 in the singular', async () => {
		renderOwner(undefined, 'fr');
		await fireEvent.click(screen.getByRole('button', { name: 'Choisir ma vitrine' }));
		expect(screen.getByRole('status')).toHaveTextContent('0 badge choisi sur 3');
	});
});
